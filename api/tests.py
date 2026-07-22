from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from api import services
from api.models import ConnectionRequest, PasswordResetOTP, UserProfile


class DistanceAndDirectionTests(TestCase):
    def test_haversine_known_distance(self):
        # بغداد تقريباً: 33.3152, 44.3661
        d = services.haversine_distance(33.3152, 44.3661, 33.3152, 44.3661)
        self.assertEqual(d, 0.0)

    def test_haversine_positive_for_different_points(self):
        d = services.haversine_distance(33.3152, 44.3661, 33.40, 44.45)
        self.assertGreater(d, 0)
        self.assertLess(d, 20)

    def test_direction_returns_string(self):
        direction = services.direction_name(33.3152, 44.3661, 34.0, 45.0)
        self.assertIn(direction, ['شمال', 'شمال شرق', 'شرق', 'جنوب شرق',
                                   'جنوب', 'جنوب غرب', 'غرب', 'شمال غرب'])


class OnlineStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', password='pass1234')
        self.profile = self.user.profile

    def test_recent_update_is_online(self):
        self.profile.last_seen = timezone.now()
        self.assertTrue(services.is_profile_online(self.profile))

    def test_stale_update_is_offline(self):
        self.profile.last_seen = timezone.now() - timedelta(minutes=30)
        self.assertFalse(services.is_profile_online(self.profile))

    def test_no_last_seen_is_offline(self):
        self.profile.last_seen = None
        self.assertFalse(services.is_profile_online(self.profile))


class NearbyPrivacyTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username='a', password='pass1234')
        self.b = User.objects.create_user(username='b', password='pass1234')
        self.pa = self.a.profile
        self.pb = self.b.profile
        self.pa.latitude, self.pa.longitude = 33.3152, 44.3661
        self.pa.save()
        self.pb.latitude, self.pb.longitude = 33.3160, 44.3670
        self.pb.display_name = 'Person B'
        self.pb.instagram_handle = 'personb'
        self.pb.save()

    def test_instagram_public_but_email_hidden_without_connection(self):
        nearby, _ = services.get_nearby_people(self.pa)
        self.assertTrue(nearby)
        person = nearby[0]
        # الإنستغرام متاح للتواصل العام بدون طلب
        self.assertIn('instagram_handle', person)
        self.assertTrue(person['instagram_handle'])
        # البريد يبقى مخفياً حتى قبول اتصال (الواتساب)
        self.assertNotIn('email', person)

    def test_ghost_excluded(self):
        self.pb.visibility_level = 'GHOST'
        self.pb.save()
        nearby, _ = services.get_nearby_people(self.pa)
        self.assertEqual(len(nearby), 0)

    def test_email_revealed_after_accepted_connection(self):
        ConnectionRequest.objects.create(
            sender=self.pa.user, receiver=self.pb.user, status='ACCEPTED')
        nearby, _ = services.get_nearby_people(self.pa)
        person = nearby[0]
        self.assertIn('email', person)


class OTPTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='c', password='pass1234')
        self.profile = self.user.profile
        self.profile.phone_number = '0790000000'
        self.profile.save()

    def test_generate_and_verify_otp(self):
        otp = services.generate_otp('0790000000')
        self.assertIsNotNone(otp)
        verified = services.verify_otp('0790000000', otp.code)
        self.assertIsNotNone(verified)

    def test_wrong_code_returns_none(self):
        services.generate_otp('0790000000')
        self.assertIsNone(services.verify_otp('0790000000', '000000'))

    def test_respect_cooldown(self):
        services.generate_otp('0790000000')
        self.assertIsNone(services.generate_otp('0790000000'))

    def test_expired_otp_invalid(self):
        otp = services.generate_otp('0790000000')
        PasswordResetOTP.objects.filter(id=otp.id).update(
            created_at=timezone.now() - timedelta(minutes=60)
        )
        self.assertIsNone(services.verify_otp('0790000000', otp.code))
