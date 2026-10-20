---
name: stitch-design
description: Use ONLY when the task involves Google Stitch designs for the biozone project (new screens, refinements, tokens, tracking). Defines biozone's stack, Stitch's reference-only role, mandatory steps, and the designs log.
---

# Stitch لتصاميم biozone — ملف المتابعة

## 1) مشروع biozone باختصار (للوكيل)

- متجر أدوية + واجهة ستاف مبنية على **Frappe/ERPNext v16** (`biozone_web`).
- الواجهات قوالب **Jinja/HTML** عربية **RTL** تُعرض من السيرفر (ليست React ولا تطبيقًا منفصلًا).
- النطاقات: المتجر `biozone.pro` + الستاف `staff.biozone.pro` + الديسك `app.biozone.pro`.

## 2) دور Stitch هنا (حد ملزم)

- Stitch **مرجع تصميم فقط**: توليد شاشات + استخراج tokens (ألوان/خطوط/مسافات/مكونات).
- **ممنوع** حقن كود Stitch الخام (React/Tailwind/Flutter) في قوالب `biozone_web` — التنفيذ النهائي دائمًا بيد المطور في كود المشروع.
- **الوضع الافتراضي: مشروع Stitch جديد لكل مهمة** — أي مهمة تُبنى في مشروع Stitch جديد ولا تُعَدَّل مشاريع قائمة. إعادة استخدام مشروع قائم ممنوعة إلا بأمر صريح.
- أي تصميم جديد يُسجَّل في جدول §4 قبل اعتباره منجزًا.

## 3) شرط إظهار الخطوات (إلزامي)

في **كل** مهمة Stitch، يعرض الوكيل أولًا قائمة الخطوات المرقمة التي سينفذها وينتظر تأكيد المستخدم قبل التنفيذ — بلا استثناء.

## 4) خطوات العمل القياسية

1. حدد الشاشة المطلوبة من جدول المتابعة (أو أضف صفًا جديدًا).
2. اطلب من Stitch (عبر MCP) التوليد/التعديل — اذكر: عربي RTL + ألوان المشروع + نوع الصفحة (متجر/ستاف).
3. استخرج الـtokens في ردك (hex + خطوط + مقاسات) — لا تكتفِ بالكود.
4. نفّذ في قالب المشروع المعني يدويًا (ملف:سطر)، ثم اعرض diff.
5. حدّث صف التصميم (الحالة + الملفات الممسوسة + التاريخ).
6. STOP — لا تنتقل لتصميم تالٍ قبل إغلاق الحالي.

## 5) جدول متابعة التصاميم

| التصميم | النوع (متجر/ستاف) | الحالة (مقترح/قيد التصميم/مستخرج/منفذ) | الـtokens | ملفات المشروع | التاريخ |
|---|---|---|---|---|---|
| مثال: صفحة دخول الستاف | ستاف | مقترح | — | — | — |
| قسم براندات المنتجات (هوم المتجر) | متجر | منفذ | primary #00685f، primary-container #008378، surface #f8f9ff، card #ffffff، outline-variant #bcc9c6، خط Tajawal، rounded-xl/8px، shadow-sm | `biozone_web/www/biozone-home.html`، `biozone_web/www/biozone_home.py`، `biozone_web/public/images/biozone-favicon.svg` | 2026-10-16 |
| هوم المتجر الكامل (هيرو + ثقة + تصنيفات 2×2 + مميزة + براندات) | متجر | منفذ | primary #00685f، bg #f8f9ff، card #ffffff، حد البطاقة #d3e4fe، text #0b1c30، muted #3d4947، خط Tajawal، بطاقة `rounded-xl` + حد + ظل ناعم (نمط الكتالوج حرفيًا)، أزرار pill | `biozone_web/www/biozone-home.html` (مشروع Stitch `14462690318905207236`، brief صارم) | 2026-10-16 |
| هوم المتجر — تطبيق تصميم المالك (zip) | متجر | منفذ | نفس tokens الصف السابق (primary #00685f، card #ffffff، حد #d3e4fe، text #0b1c30، muted #3d4947، Tajawal، `rounded-xl`) | `biozone_web/www/biozone-home.html` (تصميم المالك `stitch_biozone.zip` → `_2`: الهيرو فارغ، شريط ثقة أفقي 3 عناصر، «تصفح حسب التصنيف» 2 أعمدة، «تصفح حسب المنتج» + «عرض الكل» chevron، براندات 6 مونوغرام) | 2026-10-16 |
| شعار «Biozone» بالإنجليزية (للهيرو) | متجر | مستخرج (مرجع) | primary #00685f، mint accent #00a896، خلفية #ffffff، خط sans-serif هندسي عريض، قفل شعار أفقي مركزي | مشروع Stitch `11452885425790672161` (screen `bccc9f163e55497dae55fce143857841`، SVG 1000×400، IMAGE) | 2026-10-16 |
| بانر الهيرو بصورة فوتوغرافية | متجر | **منفذ من تصدير المالك** `stitch_biozone_hero_banner/{code.html,screen.png}` (توليد MCP فشل بمهلة مرتين — المشروع `2134443165717181340`) | خلفية صيدلية (١٣٧٦×٧٦٨) + تعتيم متدرج #00685f من اليمين (95→80% حتى 55% ثم شفاف) + طبقة #004d46 بـmultiply + عنوان أبيض 64px + زر أبيض بنص primary وسهم `arrow_back` | `biozone_web/www/biozone-home.html`، `public/images/hero/hero-pharmacy.{webp,jpg}` | 2026-10-17 |
| قسما منتجات (عطور + العناية الشخصية) + wordmarks براندات | متجر | منفذ | نفس tokens (primary #00685f، mint #00a896، card #ffffff، حد #d3e4fe، rounded-xl)، wordmark بخط Arial Bold letter-spaced | `biozone_web/www/biozone-home.html`، `biozone_web/www/biozone_home.py`، `biozone_web/public/images/brands/*.svg` (٦) | 2026-10-17 |
| نظام بحث وفلترة الكتالوج (بحث نصي يشمل اسم البراند + فلتر قسم + فلتر براند + شرائح فلاتر نشطة + «مسح الفلاتر») | متجر | منفذ (تصميم داخلي — بلا Stitch؛ استبدل نسخة النطاقات الأولية) | شريط GET واحد أعلى الكتالوج: حقل بحث مستدير + منتقيان (كل الأقسام/كل البراندات) من قيم DB الفعلية، شرائح `rounded-full` بحد primary/40 وخلفية primary/10، الهيدر حقل بحث واحد فقط مع حفظ الفلاتر عبر حقول مخفية | `biozone_web/www/catalog.py`، `www/catalog.html`، `templates/includes/site_header.html`، `services/brands.py` (ووردماركات الهوم) | 2026-10-17 |
| هيرو نصّي + تسمية «تسوّق حسب» + روابط البراند | متجر | منفذ | نفس tokens (primary #00685f، `rounded-full` للأزرار) | `biozone_web/www/biozone-home.html` (هيرو باسم Biozone + تعريف + CTA)، `biozone_web/www/catalog.py` + `catalog.html` (فلتر `brand`)، `biozone_web/www/biozone_home.py` | 2026-10-16 |
| صفحة المنتج (product detail) | متجر | أُعيد تنسيقها بمواصفات المالك المباشرة 2026-10-18 (المرجع المصدَّر `stitch_product_page_redesign/` مرفوض بقرار المالك كمرجع): بطاقة `max-w-6xl` متوازنة، عمودان متقاربان متوسطا المحاذاة عموديًا (**صورة يمين/معلومات يسار** RTL — عُكست بطلب المالك)، صورة أكبر بلا قصّ، التسلسل: اسم ← سعر (`font-extrabold`) ← زر سلة **عريض داخل العمود** (شكل التصميم السابق `rounded-xl`+ظل، مسار compact فقط) ← علامة/وصف، خبز تنقل أخف، شريط الثقة المختصر أسفل المنتج، حالة بلا صورة = placeholder البطاقات؛ محفوظ من المراحل السابقة: صندوق السعر والتسمية، الستبر المربع (compact) | tokens المشروع (primary #00685f، primary-light #e6f3f2، borderSubtle، surfaceMuted، Tajawal) | تنفيذ في `biozone_web/www/item.html` + فرع `compact` في `templates/includes/product_card.html` + `trust_strip.html` (CSS: app.8214597b، بعد تحديث السمة العام 2026-10-18: خلفية `appBg` → slate-100 على صفحات المتجر الثلاث، ظلال `shadow-sm` + حدود على البطاقات، خط فصل للهيدر `border-outline-variant`؛ اختبار إضافة السلة الفعلي + لقطات 1440/390 بصورة وبدون سليمة) | 2026-10-18 |
| كارت الصنف — التصميم الجديد (`stitch_product_page_redesign2`) | متجر | منفذ | بطاقة `rounded-3xl` 24px بحد slate-100/80 وظل مخصص + ارتفاع hover؛ بئر صورة **4:5** بتدرج slate-50→primary-light/30 و`mix-blend-multiply` + تكبير hover؛ اسم مركزي (text-sm)؛ وسم القسم pill أسفل الاسم؛ فاصل + صف سفلي: سعر `text-xl font-extrabold` + ج.م + «سعر القطعة» — زر «أضف» mint (`bg-primary-light`, h-9) وستبر 28px (− يمين/+ يسار)؛ أُسقطت الشارات والقلب بقرار المالك (لا بيانات/ميزة)؛ محوّلات brand-*→primary #00685f بدل #007A65 | `biozone_web/templates/includes/product_card.html` (الكتالوج+الرئيسية+المشابهة؛ فرع compact لصفحة المنتج بلا تغيير؛ CSS app.012c13b8) | 2026-10-18 |
| كتالوج new_design — شبكة + قائمة + لوحة فلاتر (تصدير المالك `new_design/blozone` + `blozone_list_view`؛ عُكس فيه Option C فبحث الهيدر ظاهر على الكتالوج، وحُذف شريطا التسوق، وأُبقيت مقاسات pp8 16/22/12؛ القلب مستبعد بقرار المالك) | متجر | منفذ | كارت شبكة `rounded-2xl` حد slate-200/80 + `shadow-card` (0 2px 8px -2px rgba(0,92,85,.05) + 0 1px 4px -1px rgba(0,0,0,.03)) و`shadow-card-hover` (0 12px 24px -6px rgba(0,92,85,.12)) + `hover:-translate-y-[3px]` 250ms؛ وسم emerald-50/primary؛ نطاق صورة `min-h-[200px] bg-slate-50/50` + `h-36` (transition-transform 300ms)؛ اسم `text-base` يمين؛ فوتر فاصل slate-100: سعر 22 primary + زر «أضف» **صلب** `bg-primary` h-9 rounded-xl، ستبر solid-primary 28px؛ شبكة `grid-cols-1 sm:2 lg:4 gap-6`؛ **صف قائمة** (حاوية `max-w-4xl` 896px ممركزة + بئر صورة 160px ديسكتوب / 96px موبايل، `sm:p-6`: وسم+اسم ← سعر+زر عمود يسار)؛ اعتماد تصميم الفلتر (`الفلتر/code.html`، 2026-10-18): الشرائح داخل سطر العنوان — براند primary-tint + قسم slate-100 + «مسح الفلاتر» rose-500، بلا شريط منفصل؛ زر «تطبيق الفلاتر (N نتائج)» من العدّاد المطبَّق أصلًا في نفس الطلب (صفر استعلامات إضافية)؛ بلا فلتر سعر (قرار المالك نهائيًا)؛ ترقيم مرقّم بأرقام عربية ونطاق؛ لوحة جانبية `max-w-sm` باختيار واحد/مجموعة + حقول مخفية GET؛ بحث هيدر `rounded-xl bg-slate-50` (أيقونة right-3.5، X left-3)؛ أرقام عربية ٠-٩ | `biozone_web/www/catalog.html`، `www/catalog.py` (`_pages_window` + سياق العدّادات)، `templates/includes/product_card.html` (ماكرو `product_card_list` + كارت جديد + زر/ستبر)، `templates/includes/site_header.html` (البحث)، `templates/includes/cart_helpers.html` (مزامنة توأم الشبكة/القائمة)، `tailwind.config.js` (ظلال)، `tests/test_catalog_search.py` (عقدان محدَّثان) — CSS app.ea9822cc (سلسلة: app.012c13b8 → 1d9e7987 → f1dec64b → fe3cc3a4 → الحالي) | 2026-10-18 |


## 6) حدود تشغيلية

- حصة Stitch ~350 توليدًا/شهر — لا توليدات تجريبية عبثية.
- مفتاح API ينتهي (~90 يومًا) — عند فشل المصادقة: ولّد مفتاحًا وحدّث `opencode.jsonc`.
- عند `Failed to get tools`: حدّث opencode واعد التشغيل قبل أي تشخيص آخر.
