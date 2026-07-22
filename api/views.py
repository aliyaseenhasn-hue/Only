import json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from geopy.geocoders import Nominatim

from .models import UserProfile, ContactHistory, Interest


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
        
        # جلب اسم المنطقة
        if profile.latitude and profile.longitude:
            try:
                geolocator = Nominatim(user_agent="radar_app")
                location = geolocator.reverse(f"{profile.latitude}, {profile.longitude}", language='ar')
                if location:
                    # محاولة استخراج اسم المنطقة أو المدينة
                    address = location.raw.get('address', {})
                    profile.area_name = address.get('suburb') or address.get('neighbourhood') or address.get('city') or address.get('town') or "منطقة غير معروفة"
            except Exception:
                profile.area_name = "تعذر جلب المنطقة"

        profile.save()
        profile.is_online = True
        profile.save(update_fields=['is_online', 'area_name'])
        return JsonResponse({
            'success': True,
            'message': 'تم حفظ الموقع بنجاح',
            'latitude': profile.latitude,
            'longitude': profile.longitude,
            'area_name': profile.area_name,
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


def haversine_distance(lat1, lon1, lat2, lon2):
    import math
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 2)


def direction_name(lat1, lon1, lat2, lon2):
    import math
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2 - lon1))
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    if bearing < 22.5 or bearing >= 337.5: return 'شمال'
    if 22.5 <= bearing < 67.5: return 'شمال شرق'
    if 67.5 <= bearing < 112.5: return 'شرق'
    if 112.5 <= bearing < 157.5: return 'جنوب شرق'
    if 157.5 <= bearing < 202.5: return 'جنوب'
    if 202.5 <= bearing < 247.5: return 'جنوب غرب'
    if 247.5 <= bearing < 292.5: return 'غرب'
    return 'شمال غرب'


@login_required(login_url='login-page')
def radar_dashboard(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username}
    )
    all_profiles = UserProfile.objects.exclude(user=request.user).filter(
        latitude__isnull=False, longitude__isnull=False
    ).exclude(visibility_level='GHOST')
    
    # فلترة حسب الجنس إذا اختار المستخدم
    if profile.visibility_level == 'GENDER':
        all_profiles = all_profiles.filter(gender=profile.gender)
    nearby_people = []
    current_location_available = profile.latitude is not None and profile.longitude is not None
    new_found_contacts = []

    if current_location_available:
        for item in all_profiles:
            distance = haversine_distance(profile.latitude, profile.longitude, item.latitude, item.longitude)
            # إذا كان الشخص ضمن 2.5 كم
            if distance <= 2.5:
                person_data = {
                    'id': item.user.id,
                    'display_name': item.display_name,
                    'email': item.user.email,
                    'instagram_handle': item.instagram_handle,
                    'avatar_url': item.avatar.url if item.avatar else (item.avatar_url or 'https://ui-avatars.com/api/?name=' + item.display_name.replace(' ', '+')),
                    'distance': distance,
                    'direction': direction_name(profile.latitude, profile.longitude, item.latitude, item.longitude),
                    'area_name': item.area_name,
                    'is_online': item.is_online,
                    'intent_display': item.get_current_intent_display(),
                    'latitude': item.latitude,
                    'longitude': item.longitude,
                }
                nearby_people.append(person_data)

                # سجل في ContactHistory إذا أول مرة نلقاه اليوم
                today = timezone.now().date()
                already_logged = ContactHistory.objects.filter(
                    user=request.user,
                    found_user=item.user,
                    found_at__date=today,
                ).exists()
                if not already_logged:
                    ContactHistory.objects.create(
                        user=request.user,
                        found_user=item.user,
                        found_user_display=item.display_name,
                        found_user_instagram=item.instagram_handle,
                        latitude=profile.latitude,
                        longitude=profile.longitude,
                        distance=distance,
                        direction=direction_name(profile.latitude, profile.longitude, item.latitude, item.longitude),
                    )
                    # إضافة نقاط اكتشاف
                    profile.discovery_points += 10
                    profile.save(update_fields=['discovery_points'])
                    new_found_contacts.append(person_data)

        nearby_people.sort(key=lambda item: item['distance'])

    if not current_location_available and all_profiles.exists():
        for item in all_profiles[:5]:
            nearby_people.append({
                'display_name': item.display_name,
                'email': item.user.email,
                'instagram_handle': item.instagram_handle,
                'avatar_url': item.avatar_url or 'https://ui-avatars.com/api/?name=' + item.display_name.replace(' ', '+'),
                'distance': None,
                'direction': 'غير متوفر',
                'is_online': item.is_online,
            })

    events = [
        {'place': 'مقهى المدينة', 'title': 'لقاء محبي التقنية', 'time': 'اليوم ٧:٠٠ م'},
        {'place': 'المنتزه المركزي', 'title': 'جولة رياضية مفتوحة', 'time': 'غدًا ١٠:٠٠ ص'},
        {'place': 'مكتبة الأصدقاء', 'title': 'ورش عمل ثقافية', 'time': 'بعد ساعتين'},
    ]

    online_count = sum(1 for person in nearby_people if person['is_online'])
    stats = {
        'nearby_count': len(nearby_people),
        'online_count': online_count,
        'expected_participants': len(nearby_people) * 3 if nearby_people else 20,
        'invited_friends': 16,
    }
    total_contacts = ContactHistory.objects.filter(user=request.user).count()

    # تحضير بيانات JSON للرادار التفاعلي
    nearby_people_json = json.dumps({
        'people': [
            {
                'id': p.get('id'),
                'display_name': p['display_name'],
                'latitude': p.get('latitude'),
                'longitude': p.get('longitude'),
                'avatar_url': p.get('avatar_url'),
                'intent': p.get('intent_display'),
                'is_online': p['is_online'],
                'distance': p['distance'],
            }
            for p in nearby_people if p.get('latitude')
        ],
        'myLat': profile.latitude,
        'myLng': profile.longitude,
    })

    return render(request, 'radar_dashboard.html', {
        'user_profile': profile,
        'nearby_people': nearby_people,
        'events': events,
        'stats': stats,
        'current_location_available': current_location_available,
        'new_found_contacts': new_found_contacts,
        'total_contacts': total_contacts,
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


def reset_password_screen(request):
    """إعادة تعيين كلمة السر باستخدام رقم الهاتف"""
    if request.method == 'POST':
        phone = request.POST.get('phone')
        new_password = request.POST.get('new_password')
        new_password_confirm = request.POST.get('new_password_confirm')

        try:
            profile = UserProfile.objects.get(phone_number=phone)
        except UserProfile.DoesNotExist:
            messages.error(request, 'رقم الهاتف غير مسجل.')
            return render(request, 'reset_password.html')

        if new_password != new_password_confirm:
            messages.error(request, 'كلمتا المرور غير متطابقتين.')
            return render(request, 'reset_password.html')

        if len(new_password) < 6:
            messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل.')
            return render(request, 'reset_password.html')

        profile.user.set_password(new_password)
        profile.user.save()
        messages.success(request, 'تم إعادة تعيين كلمة السر بنجاح ✅')
        return redirect('login-page')

    return render(request, 'reset_password.html')


@login_required(login_url='login-page')
def discovery_screen(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username}
    )
    all_profiles = UserProfile.objects.exclude(user=request.user).filter(
        latitude__isnull=False, longitude__isnull=False
    ).exclude(visibility_level='GHOST')
    
    # فلترة حسب الجنس إذا اختار المستخدم
    if profile.visibility_level == 'GENDER':
        all_profiles = all_profiles.filter(gender=profile.gender)
    nearby_people = []
    current_location_available = profile.latitude is not None and profile.longitude is not None

    if current_location_available:
        for item in all_profiles:
            distance = haversine_distance(profile.latitude, profile.longitude, item.latitude, item.longitude)
            if distance <= 2.5:
                nearby_people.append({
                    'id': item.user.id,
                    'display_name': item.display_name,
                    'instagram_handle': item.instagram_handle,
                    'avatar_url': item.avatar.url if item.avatar else (item.avatar_url or 'https://ui-avatars.com/api/?name=' + item.display_name.replace(' ', '+')),
                    'distance': distance,
                    'direction': direction_name(profile.latitude, profile.longitude, item.latitude, item.longitude),
                    'area_name': item.area_name,
                    'is_online': item.is_online,
                    'intent_display': item.get_current_intent_display(),
                    'last_seen': item.last_seen,
                })
        nearby_people.sort(key=lambda x: x['distance'])

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
        distance = haversine_distance(my_profile.latitude, my_profile.longitude, target_profile.latitude, target_profile.longitude)
        direction = direction_name(my_profile.latitude, my_profile.longitude, target_profile.latitude, target_profile.longitude)

    return render(request, 'user_profile.html', {
        'target_profile': target_profile,
        'distance': distance,
        'direction': direction,
    })


@login_required(login_url='login-page')
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('radar-dashboard')
    
    users = UserProfile.objects.select_related('user').all().order_by('-last_seen')
    
    # الإحصائيات
    stats = {
        'total_users': User.objects.count(),
        'online_users': UserProfile.objects.filter(is_online=True).count(),
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
