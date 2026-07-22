"""منطق مشترك لتطبيق api: المسافة، الاتجاه، حالة الاتصال، القريبين، و OTP.

الهدف: إزالة التكرار بين radar_dashboard و discovery_screen وإبقاء العروض رفيعة.
"""
import logging
import math
import random
from datetime import timedelta
from time import time

from django.conf import settings
from django.utils import timezone

from .models import ConnectionRequest, ContactHistory, PasswordResetOTP, UserProfile

logger = logging.getLogger(__name__)

# كاش بسيط داخل الذاكرة لنتائج الترميز العكسي لتقليل استدعاءات Nominatim.
_REVERSE_GEOCODE_CACHE = {}
_REVERSE_GEOCODE_TTL = 6 * 3600  # ثوانٍ


def haversine_distance(lat1, lon1, lat2, lon2):
    """المسافة بالكيلومتر بين نقطتين جغرافيتين."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 2)


_DIRECTIONS = [
    (22.5, 'شمال'), (67.5, 'شمال شرق'), (112.5, 'شرق'), (157.5, 'جنوب شرق'),
    (202.5, 'جنوب'), (247.5, 'جنوب غرب'), (292.5, 'غرب'), (337.5, 'شمال غرب'),
]


def direction_name(lat1, lon1, lat2, lon2):
    """اسم الاتجاه الجغرافي بالعربية من النقطة 1 إلى النقطة 2."""
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2 - lon1)))
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    for limit, name in _DIRECTIONS:
        if bearing < limit:
            return name
    return 'شمال'


def is_profile_online(profile, now=None):
    """اعتبار المستخدم متصلاً إذا حدّث موقعه خلال آخر X دقيقة (بدل قيمة is_online الثابتة)."""
    now = now or timezone.now()
    threshold = now - timedelta(minutes=settings.ONLINE_THRESHOLD_MINUTES)
    return profile.last_seen is not None and profile.last_seen >= threshold


def _avatar_for(profile):
    if profile.avatar:
        return profile.avatar.url
    if profile.avatar_url:
        return profile.avatar_url
    return 'https://ui-avatars.com/api/?name=' + (profile.display_name or '').replace(' ', '+')


def get_nearby_people(profile, include_sensitive=False):
    """قائمة الأشخاص القريبين ضمن النطاق.

    الخصوصية: لا تُعاد الإحداثيات الدقيقة ولا البريد ولا حساب الإنستغرام للعملاء
    إلا إذا كان include_sensitive=True (مثلاً بعد قبول طلب اتصال).
    """
    radius = settings.NEARBY_RADIUS_KM
    if not profile.location_available():
        return [], []

    qs = (UserProfile.objects.exclude(user=profile.user)
          .filter(latitude__isnull=False, longitude__isnull=False)
          .exclude(visibility_level='GHOST'))

    if profile.visibility_level == 'GENDER' and profile.gender:
        qs = qs.filter(gender=profile.gender)

    nearby = []
    new_contacts = []
    today = timezone.now().date()

    for item in qs:
        distance = haversine_distance(profile.latitude, profile.longitude, item.latitude, item.longitude)
        if distance > radius:
            continue

        connected = ConnectionRequest.objects.filter(
            sender=profile.user, receiver=item.user, status='ACCEPTED'
        ).exists() or ConnectionRequest.objects.filter(
            sender=item.user, receiver=profile.user, status='ACCEPTED'
        ).exists()

        person = {
            'id': item.user.id,
            'display_name': item.display_name,
            'distance': distance,
            'direction': direction_name(profile.latitude, profile.longitude, item.latitude, item.longitude),
            'area_name': item.area_name,
            'is_online': is_profile_online(item),
            'intent_display': item.get_current_intent_display(),
            'avatar_url': _avatar_for(item),
            # الإنستغرام للتواصل العام بدون طلب
            'instagram_handle': item.instagram_handle,
        }
        # بيانات حساسة (البريد) تُكشف فقط بعد قبول اتصال (الواتساب)
        if include_sensitive or connected:
            person['email'] = item.user.email
        nearby.append(person)

        # سجل في ContactHistory إذا أول مرة نلقاه اليوم
        already = ContactHistory.objects.filter(
            user=profile.user, found_user=item.user, found_at__date=today
        ).exists()
        if not already:
            ContactHistory.objects.create(
                user=profile.user, found_user=item.user,
                found_user_display=item.display_name,
                found_user_instagram=item.instagram_handle,
                latitude=profile.latitude, longitude=profile.longitude,
                distance=distance,
                direction=person['direction'],
            )
            new_contacts.append(person)

    nearby.sort(key=lambda p: p['distance'])
    return nearby, new_contacts


def reverse_geocode(latitude, longitude, language='ar'):
    """اسم المنطقة من الإحداثيات مع تخزين مؤقت لتقليل ضغط Nominatim."""
    key = (round(latitude, 4), round(longitude, 4))
    cached = _REVERSE_GEOCODE_CACHE.get(key)
    if cached and (time() - cached[0]) < _REVERSE_GEOCODE_TTL:
        return cached[1]

    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="radar_app")
        location = geolocator.reverse(f"{latitude}, {longitude}", language=language)
        if location:
            address = location.raw.get('address', {})
            area = (address.get('suburb') or address.get('neighbourhood')
                    or address.get('city') or address.get('town')
                    or "منطقة غير معروفة")
            _REVERSE_GEOCODE_CACHE[key] = (time(), area)
            return area
    except Exception:
        logger.warning("reverse geocode failed for %s,%s", latitude, longitude, exc_info=True)
    return "تعذر جلب المنطقة"


# ---------------- OTP ----------------

def generate_otp(phone_number):
    """إنشاء رمز OTP جديد وإبطال السابق، مع احترام فترة التهدئة."""
    recent = PasswordResetOTP.objects.filter(
        phone_number=phone_number,
        created_at__gte=timezone.now() - timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS),
    ).first()
    if recent:
        return None  # ضمن فترة التهدئة

    PasswordResetOTP.objects.filter(phone_number=phone_number, used=False).update(used=True)
    digits = settings.PASSWORD_RESET_OTP_LENGTH
    code = ''.join(str(random.randint(0, 9)) for _ in range(digits))
    otp = PasswordResetOTP.objects.create(phone_number=phone_number, code=code)
    logger.info("OTP generated for %s", phone_number)
    return otp


def verify_otp(phone_number, code):
    """التحقق من صحة الرمز وعدم انتهائه. تُعيد كائن OTP أو None."""
    expiry = timezone.now() - timedelta(minutes=settings.PASSWORD_RESET_OTP_EXPIRY_MINUTES)
    return PasswordResetOTP.objects.filter(
        phone_number=phone_number, code=code, used=False, created_at__gte=expiry
    ).order_by('-created_at').first()
