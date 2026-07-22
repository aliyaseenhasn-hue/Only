# رادار اجتماعي

تطبيق Django بسيط لاستكشاف المستخدمين القريبين بناءً على الموقع، مع واجهة عربية وتصميم PWA بسيط.

## المتطلبات

- Python 3.14
- بيئة افتراضية (`venv`)

## التثبيت

1. افتح الطرفية في مجلد المشروع:
   ```powershell
   cd "c:\Users\Click Tech\myprojects"
   ```
2. فعّل البيئة الافتراضية:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
3. ثبّت المتطلبات:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. شغّل الترحيلات:
   ```powershell
   python manage.py migrate
   ```
5. أنشئ مستخدمًا إداريًا (اختياري):
   ```powershell
   python manage.py createsuperuser
   ```

## التشغيل

```powershell
python manage.py runserver
```

ثم افتح المتصفح على:

```text
http://127.0.0.1:8000/api/login-page/
```

أو انتقل إلى:

```text
http://127.0.0.1:8000/
```

## النشر على PythonAnywhere

1. سجّل الدخول إلى حسابك في PythonAnywhere.
2. في صفحة "Web" أنشئ تطبيق ويب جديد واختر Python 3.11 أو 3.12 (أو الإصدار المتاح الأقرب).
3. في قسم "Source code" ضع مسار مجلد المشروع، مثل:
   ```text
   /home/yourusername/myprojects
   ```
4. في قسم "Virtualenv" اختر أو أنشئ بيئة افتراضية، ثم ثبّت المتطلبات:
   ```bash
   source /home/yourusername/.virtualenvs/myprojects/bin/activate
   pip install -r /home/yourusername/myprojects/requirements.txt
   ```
5. في قسم "WSGI configuration file" تأكد من أن التطبيق يستخدم:
   ```python
   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nearby_radar.settings')
   ```
6. أضف متغيرات البيئة في صفحة "Web" ضمن "Environment variables":
   ```text
   DJANGO_SECRET_KEY=your-secret-key
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=yourusername.pythonanywhere.com
   ```
7. قم بتشغيل الترحيلات:
   ```bash
   cd /home/yourusername/myprojects
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```
8. في صفحة "Web" اضاف مسار ثابت Static files من:
   ```text
   URL: /static/
   Directory: /home/yourusername/myprojects/staticfiles
   ```
9. أعد تحميل التطبيق من لوحة PythonAnywhere.

## ملاحظات

- قمت بتحديث ملف `static/manifest.json` ليبدأ التطبيق عند المسار الصحيح `/api/radar/`.
- أضفت حقلَي الإحداثيات في صفحة التسجيل والحساب الشخصي ليصبح التطبيق أكثر اكتمالًا.
- أضفت دعم إنشاء ملف تعريف تلقائيًا عند إنشاء مستخدم جديد باستخدام إشارة `post_save`.
- عدلت `nearby_radar/settings.py` لدعم إعدادات البيئة مثل `DJANGO_DEBUG` و`DJANGO_ALLOWED_HOSTS`.
- تأكد من السماح باستخدام الموقع في المتصفح حتى تعمل خاصية تحديد الموقع التلقائي.
