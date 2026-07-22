from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Interest(models.Model):
    name = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Material Symbol Name")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "اهتمام"
        verbose_name_plural = "الاهتمامات"


class UserProfile(models.Model):
    GENDER_CHOICES = (
        ('M', 'ذكر'),
        ('F', 'أنثى'),
    )
    VISIBILITY_CHOICES = (
        ('ALL', 'الجميع'),
        ('GENDER', 'نفس جنسي فقط'),
        ('GHOST', 'وضع التخفي (Ghost)'),
    )
    INTENT_CHOICES = (
        ('NONE', 'متاح فقط'),
        ('CHAT', 'مستعد للدردشة'),
        ('COFFEE', 'أبحث عن شريك قهوة'),
        ('TECH', 'نقاش تقني'),
        ('HIRE', 'فرصة عمل / تعاون'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    
    # ميزات جديدة: الخصوصية والحالة والدردشة
    visibility_level = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='ALL')
    current_intent = models.CharField(max_length=10, choices=INTENT_CHOICES, default='NONE')
    discovery_points = models.IntegerField(default=0)

    instagram_handle = models.CharField(max_length=100) # تم جعله إجبارياً
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    interests_list = models.ManyToManyField(Interest, blank=True, related_name='profiles')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    area_name = models.CharField(max_length=255, blank=True, null=True)
    is_online = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.username

    def location_available(self):
        return self.latitude is not None and self.longitude is not None

    def to_dict(self):
        return {
            'id': self.user.id,
            'email': self.user.email,
            'display_name': self.display_name,
            'instagram_handle': self.instagram_handle,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_online': self.is_online,
        }


class ContactHistory(models.Model):
    """سجل اللقاءات مع الأشخاص القريبين"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contacts_found')
    found_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contacts_found_by')
    found_user_display = models.CharField(max_length=120)
    found_user_instagram = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    distance = models.FloatField()
    direction = models.CharField(max_length=20, default='غير متوفر')
    found_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-found_at']
        verbose_name = 'سجل لقاء'
        verbose_name_plural = 'سجل اللقاءات'

    def __str__(self):
        return f'{self.user.username} ⇢ {self.found_user_display} @ {self.found_at.strftime("%Y-%m-%d %H:%M")}'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, display_name=instance.username)


class ConnectionRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    status = models.CharField(max_length=20, choices=(
        ('PENDING', 'قيد الانتظار'),
        ('ACCEPTED', 'تم القبول'),
        ('REJECTED', 'تم الرفض')
    ), default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')
        verbose_name = 'طلب اتصال'
        verbose_name_plural = 'طلبات الاتصال'

    def __str__(self):
        return f'{self.sender.username} -> {self.receiver.username} ({self.status})'
