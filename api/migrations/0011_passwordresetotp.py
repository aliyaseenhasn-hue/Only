from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_alter_userprofile_instagram_handle_connectionrequest'),
    ]

    operations = [
        migrations.CreateModel(
            name='PasswordResetOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(db_index=True, max_length=20)),
                ('code', models.CharField(max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'رمز إعادة تعيين',
                'verbose_name_plural': 'رموز إعادة التعيين',
                'ordering': ['-created_at'],
            },
        ),
    ]
