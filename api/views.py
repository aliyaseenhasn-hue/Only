import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from . import services
from .models import ConnectionRequest, ContactHistory, Interest, UserProfile

logger = logging.getLogger('api')


def authenticate_by_phone_or_username(request, identifier, password):
    user = authenticate(request, username=identifier, password=password)
    if user:
        return user
    try:
        profile = UserProfile.objects.get(phone_number=identifier)
        return authenticate(request, username=profile.user.username, password=password)
    except UserProfile.DoesNotExist:
        return None


def login_screen(request):
    if request.method == 'POST':
        identifier = request.POST.get('phone')
        password = request.POST.get('password')
        user = authenticate_by_phone_or_username(request, identifier, password)
        if user is not None:
            login(request, user)
            return redirect('radar-dashboard')
        messages.error(request, 'بيانات الدخول غير صحيحة أو الحساب غير موجود.')
    return render(request, 'login.html')


def register_screen(request):
    interests_all = Interest.objects.all()
    if request.method == 'POST':
        phone = request.POST.get('phone')
        username = request.POST.get('username')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        gender = request.POST.get('gender')
        display_name = request.POST.get('display_name') or username
        instagram_handle = request.POST.get('instagram_handle', '')
        bio = request.POST.get('bio', '')
        selected_interests = request.POST.getlist('interests')

        if not phone or len(phone) < 10:
            messages.error(request, 'يرجى إدخال رقم هاتف صحيح.')
        elif not instagram_handle:
            messages.error(request, 'حساب الانستقرام إلزامي.')
        elif password != password_confirm:
            messages.error(request, 'كلمتا المرور غير متطابقتين.')
        elif len(password) < 6:
            messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'اسم المستخدم مستخدم بالفعل.')
        elif UserProfile.objects.filter(phone_number=phone).exists():
            messages.error(request, 'رقم الهاتف مستخدم بالفعل.')
        else:
            user = User.objects.create_user(username=username, password=password)
            profile = UserProfile.objects.get(user=user)
            profile.display_name = display_name
            profile.phone_number = phone
            profile.gender = gender
            profile.instagram_handle = instagram_handle
            profile.bio = bio
            profile.interests_list.set(selected_interests)
            profile.save()
            messages.success(request, 'تم إنشاء الحساب بنجاح ✅')
            return redirect('login-page')
    return render(request, 'register.html', {'interests_all': interests_all})


@login_required(login_url='login-page')
def profile_screen(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username}
    )
    interests_all = Interest.objects.all()
    if request.method == 'POST':
        profile.display_name = request.POST.get('display_name', profile.display_name)
        profile.phone_number = request.POST.get('phone_number', profile.phone_number)
        profile.instagram_handle = request.POST.get('instagram_handle', profile.instagram_handle)
        profile.bio = request.POST.get('bio', profile.bio)

        selected_interests = request.POST.getlist('interests')
        profile.interests_list.set(selected_interests)

        # ميزات جديدة في البروفايل
        profile.visibility_level = request.POST.get('visibility_level', profile.visibility_level)
        profile.current_intent = request.POST.get('current_intent', profile.current_intent)

        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']

        profile.save()
        messages.success(request, 'تم حفظ التغييرات ✅')
        return redirect('profile-page')

    my_interests_ids = profile.interests_list.values_list('id', flat=True)
    return render(request, 'profile.html', {
        'profile': profile,
        'interests_all': interests_all,
        'my_interests_ids': my_interests_ids
    })


@login_required(login_url='login-page')
def update_location(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username}
    )
    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')
    try:
        profile.latitude = float(latitude) if latitude else None
        profile.longitude = float(longitude) if longitude else None

        # جلب اسم المنطقة (مع تخزين مؤقت لتقليل استدعاءات Nominatim)
        if profile.latitude and profile.longitude:
            profile.area_name = services.reverse_geocode(profile.latitude, profile.longitude)

        profile.is_online = True
        profile.save()
        # لا نُرجع إحداثياتنا الدقيقة ضرورةً، لكنها ملك المستخدم نفسه فلا بأس
        return JsonResponse({
            'success': True,
            'message': 'تم حفظ الموقع بنجاح',
            'area_name': profile.area_name,
            'is_online': services.is_profile_online(profile),
        })
    except (ValueError, TypeError):
        return JsonResponse({'error': 'يرجى إدخال إحداثيات صحيحة.'}, status=400)


def logout_view(request):
    logout(request)
    return redirect('login-page')


@login_required(login_url='login-page')
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, 'تم حذف حسابك نهائياً. نتمنى رؤيتك مرة أخرى.')
        return redirect('login-page')
    return redirect('profile-page')


@login_required(login_url='login-page')
def radar_dashboard(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username}
    )
    nearby_people, new_found_contacts = services.get_nearby_people(profile)

    online_count = sum(1 for person in nearby_people if person['is_online'])
    stats = {
        'nearby_count': len(nearby_people),
        'online_count': online_count,
        'expected_participants': len(nearby_people) * 3 if nearby_people else 20,
        'invited_friends': 16,
    }
    total_contacts = ContactHistory.objects.filter(user=request.user).count()

    # طلبات الاتصال الواردة
    pending_requests = ConnectionRequest.objects.filter(receiver=request.user, status='PENDING')

    # بيانات JSON للرادار التفاعلي — بدون إحداثيات دقيقة للعملاء
    nearby_people_json = json.dumps({
        'people': [
            {
                'id': p['id'],
                'display_name': p['display_name'],
                'avatar_url': p.get('avatar_url'),
                'intent': p.get('intent_display'),
                'is_online': p['is_online'],
                'distance': p['distance'],
                'direction': p['direction'],
            }
            for p in nearby_people
        ],
        'myLat': profile.latitude,
        'myLng': profile.longitude,
    })

    return render(request, 'radar_dashboard.html', {
        'user_profile': profile,
        'nearby_people': nearby_people,
        'events': [],  # مصدر بيانات فعلي لاحقاً بدل البيانات الوهمية
        'stats': stats,
        'current_location_available': profile.location_available(),
        'new_found_contacts': new_found_contacts,
        'total_contacts': total_contacts,
        'pending_requests': pending_requests,
        'nearby_people_json': nearby_people_json,
    })


@login_required(login_url='login-page')
def contact_history_view(request):
    """صفحة أرشيف اللقاءات"""
    history = ContactHistory.objects.filter(user=request.user)
    search_query = request.GET.get('q', '')
    if search_query:
        history = history.filter(found_user_display__icontains=search_query)

    # إحصائيات
    total = history.count()
    unique_people = history.values('found_user').distinct().count()
    today_count = history.filter(found_at__date=timezone.now().date()).count()

    from django.core.paginator import Paginator
    paginator = Paginator(history, 20)
    page = request.GET.get('page', 1)
    history_page = paginator.get_page(page)

    return render(request, 'contact_history.html', {
        'history': history_page,
        'total': total,
        'unique_people': unique_people,
        'today_count': today_count,
        'search_query': search_query,
    })


# ---------------- إعادة تعيين كلمة المرور عبر OTP ----------------

def reset_password_screen(request):
    """الخطوة 1: طلب رمز OTP بناءً على رقم الهاتف."""
    if request.method == 'POST':
        phone = request.POST.get('phone')
        try:
            UserProfile.objects.get(phone_number=phone)
        except UserProfile.DoesNotExist:
            messages.error(request, 'رقم الهاتف غير مسجل.')
            return render(request, 'reset_password.html', {'step': 'request'})

        otp = services.generate_otp(phone)
        if otp is None:
            messages.error(request, 'يرجى الانتظار قبل طلب رمز جديد.')
            return render(request, 'reset_password.html', {'step': 'request', 'phone': phone})

        # ملاحظة: في الإنتاج يُرسل الرمز عبر بوابة SMS. للتطوير نُظهره في الرسائل.
        if settings.DEBUG:
            messages.info(request, f'رمز التحقق (للتطوير): {otp.code}')
        else:
            messages.success(request, 'تم إرسال رمز التحقق إلى رقم هاتفك.')
        return render(request, 'reset_password.html', {'step': 'confirm', 'phone': phone})

    return render(request, 'reset_password.html', {'step': 'request'})


def reset_password_confirm(request):
    """الخطوة 2: التحقق من الرمز وتعيين كلمة المرور الجديدة."""
    if request.method != 'POST':
        return redirect('reset-password-page')

    phone = request.POST.get('phone', '')
    code = request.POST.get('code', '')
    new_password = request.POST.get('new_password', '')
    new_password_confirm = request.POST.get('new_password_confirm', '')

    otp = services.verify_otp(phone, code)
    if not otp:
        messages.error(request, 'رمز التحقق غير صحيح أو منتهي الصلاحية.')
        return render(request, 'reset_password.html', {'step': 'confirm', 'phone': phone})

    if new_password != new_password_confirm:
        messages.error(request, 'كلمتا المرور غير متطابقتين.')
        return render(request, 'reset_password.html', {'step': 'confirm', 'phone': phone})

    if len(new_password) < 6:
        messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل.')
        return render(request, 'reset_password.html', {'step': 'confirm', 'phone': phone})

    try:
        profile = UserProfile.objects.get(phone_number=phone)
    except UserProfile.DoesNotExist:
        messages.error(request, 'رقم الهاتف غير مسجل.')
        return redirect('reset-password-page')

    profile.user.set_password(new_password)
    profile.user.save()
    otp.used = True
    otp.save()
    messages.success(request, 'تم إعادة تعيين كلمة السر بنجاح ✅')
    return redirect('login-page')


@login_required(login_url='login-page')
def discovery_screen(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username}
    )
    nearby_people, _ = services.get_nearby_people(profile)
    return render(request, 'discovery.html', {
        'nearby_people': nearby_people,
        'total_found': len(nearby_people),
    })


@login_required(login_url='login-page')
def user_detail_view(request, user_id):
    try:
        target_user = User.objects.get(id=user_id)
        target_profile = target_user.profile
    except (User.DoesNotExist, UserProfile.DoesNotExist):
        return redirect('radar-dashboard')

    my_profile = request.user.profile
    distance = None
    direction = "غير متوفر"
    if my_profile.location_available() and target_profile.location_available():
        distance = services.haversine_distance(
            my_profile.latitude, my_profile.longitude,
            target_profile.latitude, target_profile.longitude)
        direction = services.direction_name(
            my_profile.latitude, my_profile.longitude,
            target_profile.latitude, target_profile.longitude)

    # التحقق من حالة الاتصال
    connection = ConnectionRequest.objects.filter(sender=request.user, receiver=target_user).first()
    if not connection:
        received_connection = ConnectionRequest.objects.filter(sender=target_user, receiver=request.user).first()
        if received_connection and received_connection.status == 'ACCEPTED':
            connection = received_connection

    # إظهار بيانات التواصل فقط بعد قبول اتصال
    connected = bool(connection and connection.status == 'ACCEPTED')

    return render(request, 'user_profile.html', {
        'target_profile': target_profile,
        'distance': distance,
        'direction': direction,
        'connection': connection,
        'show_contact_info': connected,
    })


@login_required(login_url='login-page')
def send_connection_request(request, user_id):
    if request.method == 'POST':
        try:
            receiver = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'المستخدم غير موجود.')
            return redirect('radar-dashboard')
        if receiver == request.user:
            messages.error(request, 'لا يمكنك إرسال طلب لنفسك.')
            return redirect('radar-dashboard')
        ConnectionRequest.objects.get_or_create(sender=request.user, receiver=receiver)
        messages.success(request, 'تم إرسال طلب الاتصال بنجاح.')
    return redirect('user-detail', user_id=user_id)


@login_required(login_url='login-page')
def respond_connection_request(request, request_id, action):
    try:
        conn_request = ConnectionRequest.objects.get(id=request_id, receiver=request.user)
    except ConnectionRequest.DoesNotExist:
        messages.error(request, 'طلب الاتصال غير موجود.')
        return redirect('radar-dashboard')
    if action == 'accept':
        conn_request.status = 'ACCEPTED'
        conn_request.save()
        messages.success(request, 'تم قبول طلب الاتصال.')
    elif action == 'reject':
        conn_request.status = 'REJECTED'
        conn_request.save()
        messages.info(request, 'تم رفض طلب الاتصال.')
    return redirect('radar-dashboard')


@login_required(login_url='login-page')
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('radar-dashboard')

    users = UserProfile.objects.select_related('user').all().order_by('-last_seen')

    # الإحصائيات
    stats = {
        'total_users': User.objects.count(),
        'online_users': sum(1 for p in users if services.is_profile_online(p)),
        'male_count': UserProfile.objects.filter(gender='M').count(),
        'female_count': UserProfile.objects.filter(gender='F').count(),
        'total_contacts': ContactHistory.objects.count(),
        'locations_set': UserProfile.objects.filter(latitude__isnull=False).count(),
    }

    # توزيع الاهتمامات
    top_interests = Interest.objects.annotate(user_count=Count('profiles')).order_by('-user_count')[:5]

    return render(request, 'admin_dashboard.html', {
        'users': users,
        'stats': stats,
        'top_interests': top_interests
    })
