// Privacy Policy (NA-07). Every statement must match what the code does: when a feature changes what is
// stored, shown or shared (licence uploads BU-03, VIN decoding BU-09, notifications BU-05, language
// preference HA-03), update this text and LEGAL_UPDATED in the same pull request.

import { LEGAL_UPDATED, type BilingualDocument } from './types'

export const PRIVACY_POLICY: BilingualDocument = {
  en: {
    title: 'Privacy Policy',
    updated: LEGAL_UPDATED.en,
    intro: [
      'Sijil is a demo vehicle service-history platform built as a student project for the 42 curriculum. Approved workshops and dealerships record services against a car’s VIN (chassis number), and anyone can look up that history. This policy explains what personal data Sijil keeps, why, who can see it and for how long.',
      'Sijil is not a government service and is not connected to any official UAE database, insurer or dealer system. All demo data is fictional. Please don’t enter real personal data you wouldn’t want stored in a demo.',
    ],
    sections: [
      {
        id: 'who-we-are',
        heading: 'Who is responsible',
        paragraphs: [
          'The platform administrators of the Sijil deployment you are using are responsible for the data in it. For the 42 demo deployment, these are the student team that built Sijil. Contact them about anything in this policy (see “Contact”).',
        ],
      },
      {
        id: 'what-we-collect',
        heading: 'What we collect',
        items: [
          'Account: your email address, full name and password. The password is never stored; only an Argon2id hash of it is.',
          'Role and memberships: whether you are a consumer or a platform admin, and which workshops or dealerships you belong to, with your role there (entity admin or staff) and whether the membership is active.',
          'Sessions: when you sign in we store a hash of a random session token and when the session expires or ends. We do not store your IP address or browser details with it.',
          'Businesses: for each registered workshop or dealership, its name, type, trade licence number, emirate, review status and, if rejected, the reason.',
          'Licence documents: the trade licence and similar documents a business uploads during registration, with the file name, type, size and who uploaded it.',
          'Service records: the VIN, service date, category, work done, odometer reading, mileage warnings and corrections, the name of the business that submitted the record and the name of the staff member who entered it. Staff can add a private note.',
          'Watchlists: the VINs you choose to watch. Partners’ watchlists hold VINs and a label the partner chooses.',
          'Notifications: in-app messages about records on VINs you watch and about your account or organisation.',
          'Audit log: who did what and when for sensitive actions (for example approving a business, changing a role, deleting an account), including the acting person’s email address.',
          'Technical logs: the server’s logs record the time, the address requested and the IP address of each request. Sign-in limits also count requests per IP address in memory for up to an hour.',
        ],
        paragraphs: [
          'We don’t ask for Emirates ID numbers, phone numbers or addresses, and a vehicle’s history never records who owns the car.',
        ],
      },
      {
        id: 'why',
        heading: 'Why we use it',
        items: [
          'To run your account and keep you signed in.',
          'To let approved businesses add service records, and to show those records with the business that made them.',
          'To check businesses before they can add records, using their trade licence details and documents.',
          'To tell you about new records on VINs you watch.',
          'To keep Sijil secure: preventing password guessing, investigating misuse and keeping an audit trail of sensitive changes.',
        ],
        paragraphs: ['We don’t sell data, show advertising, or use your data for profiling or marketing.'],
      },
      {
        id: 'who-sees-what',
        heading: 'Who can see what',
        items: [
          'Anyone, without signing in, can see a VIN’s history: the car’s make, model and year, service dates, categories, work done, odometer readings, mileage warnings, corrections and the name of the business that submitted each record. The PDF report shows the same.',
          'Partners holding a Sijil API key (for example a demo insurer) can read the same vehicle history through the partner API. They never receive account, staff or note data.',
          'The business that created a record can also see the staff member’s name and the private note, and can search and download its records as CSV or JSON files. Other businesses cannot.',
          'Members of a business can see its details and status; its entity admins can see and manage its members.',
          'Licence documents are visible only to the uploading business’s entity admins and to platform admins. Consumers and partners never see them. Only a platform admin can delete one, and the deletion is recorded.',
          'Platform admins can see accounts, businesses, members, all service records (including staff names and private notes) and the audit log in order to run the platform, and can search and download service records. Every download of service records is recorded in the audit log.',
        ],
      },
      {
        id: 'cookies',
        heading: 'Cookies and browser storage',
        paragraphs: ['Sijil uses two cookies, both strictly necessary, and no others:'],
        items: [
          '“sijil_session”: keeps you signed in. It holds a random token, can’t be read by page scripts (HttpOnly), is only sent over HTTPS and expires after 7 days or when you log out.',
          '“sijil_csrf”: a random value that protects forms from cross-site request forgery.',
        ],
      },
      {
        id: 'third-parties',
        heading: 'Third parties',
        paragraphs: [
          'Sijil runs on its own servers with its own database and file storage. It loads no third-party scripts, fonts, analytics or advertising, and it sends no emails.',
          'When the internet is available, Sijil may send a VIN, and only the VIN, to the US National Highway Traffic Safety Administration’s public vPIC service to look up the car’s make, model and details. Nothing about you is sent with it. Sijil works without this service.',
        ],
      },
      {
        id: 'retention',
        heading: 'How long we keep data',
        items: [
          'Service records are permanent. Vehicle history is append-only so it can be trusted: a mistake is fixed with a linked correction, never by editing or deleting the original.',
          'Accounts are kept until they are deleted. Sessions stop working after 7 days at most.',
          'When an account is deleted, its sessions, memberships, watchlists and notifications are deleted with it. Service records the person entered stay, showing the staff name as recorded at the time. Audit-log entries stay, including the email address of the person who acted.',
          'When a business is deleted, its memberships and documents go with it; its service records stay under its name as recorded.',
          'Licence documents are kept while the business exists, unless a platform admin deletes them first.',
        ],
      },
      {
        id: 'your-choices',
        heading: 'Your rights and choices',
        items: [
          'See your data: your profile shows your account details, role and memberships.',
          'Correct it: you can change your name and password yourself. To change your email address, ask a platform admin.',
          'Delete your account: ask a platform admin. Records you entered for a business stay, as explained above.',
          'Get a copy: ask a platform admin for a copy of the data held about you.',
        ],
      },
      {
        id: 'security',
        heading: 'How we protect data',
        items: [
          'All connections use HTTPS.',
          'Passwords are hashed with Argon2id. Session tokens and partner API keys are stored only as hashes.',
          'Every action checks your role and organisation on the server.',
          'Sign-in and sign-up attempts are rate-limited.',
          'Changing your password signs out every other device and starts a fresh session.',
          'Sensitive changes are recorded in the audit log.',
        ],
        paragraphs: [
          'No system is perfectly secure. If you think your account has been misused, change your password and contact a platform admin.',
        ],
      },
      {
        id: 'children',
        heading: 'Children',
        paragraphs: ['Sijil is meant for adults dealing with cars and workshops. It is not directed at children.'],
      },
      {
        id: 'changes',
        heading: 'Changes to this policy',
        paragraphs: [
          'When what Sijil stores or shares changes, this page is updated and its “Last updated” date changes. Please check it from time to time.',
        ],
      },
      {
        id: 'contact',
        heading: 'Contact',
        paragraphs: [
          'Questions or requests about your data go to the platform admins of this Sijil deployment. For the 42 demo, that is the student team that built Sijil, reachable through the project’s evaluation.',
        ],
      },
    ],
  },

  ar: {
    title: 'سياسة الخصوصية',
    updated: LEGAL_UPDATED.ar,
    intro: [
      'سجل منصة تجريبية لسجلات صيانة المركبات، أُنشئت مشروعاً طلابياً ضمن منهج 42. تسجّل الورش والوكالات المعتمدة خدمات الصيانة برقم الشاصي (VIN) للسيارة، ويمكن لأي شخص الاطلاع على هذا السجل. توضح هذه السياسة البيانات الشخصية التي تحتفظ بها سجل، وسبب ذلك، ومن يمكنه رؤيتها، ومدة الاحتفاظ بها.',
      'سجل ليست خدمة حكومية وغير مرتبطة بأي قاعدة بيانات رسمية في الإمارات أو بأي شركة تأمين أو وكالة. جميع البيانات التجريبية خيالية. يُرجى عدم إدخال بيانات شخصية حقيقية لا ترغب في تخزينها في نسخة تجريبية.',
    ],
    sections: [
      {
        id: 'who-we-are',
        heading: 'الجهة المسؤولة',
        paragraphs: [
          'مسؤولو المنصة في نسخة سجل التي تستخدمها مسؤولون عن البيانات فيها. في النسخة التجريبية لمشروع 42، هم فريق الطلاب الذي بنى سجل. تواصل معهم بشأن أي أمر في هذه السياسة (انظر «التواصل»).',
        ],
      },
      {
        id: 'what-we-collect',
        heading: 'البيانات التي نجمعها',
        items: [
          'الحساب: بريدك الإلكتروني واسمك الكامل وكلمة المرور. لا نخزّن كلمة المرور نفسها، بل بصمة مشفّرة لها بخوارزمية Argon2id.',
          'الدور والعضويات: ما إذا كنت مستهلكاً أو مسؤول منصة، والورش أو الوكالات التي تنتمي إليها، ودورك فيها (مسؤول جهة أو موظف)، وما إذا كانت العضوية نشطة.',
          'الجلسات: عند تسجيل دخولك نخزّن بصمة رمز جلسة عشوائي وموعد انتهاء الجلسة أو إنهائها. لا نخزّن معها عنوان IP أو بيانات المتصفح.',
          'المنشآت: لكل ورشة أو وكالة مسجّلة، اسمها ونوعها ورقم رخصتها التجارية والإمارة وحالة مراجعتها، وسبب الرفض إن رُفضت.',
          'مستندات الرخصة: الرخصة التجارية والمستندات المشابهة التي ترفعها المنشأة عند التسجيل، مع اسم الملف ونوعه وحجمه ومن رفعه.',
          'سجلات الصيانة: رقم الشاصي وتاريخ الخدمة والفئة والأعمال المنجزة وقراءة العداد وتحذيرات المسافة والتصحيحات، واسم المنشأة التي أضافت السجل واسم الموظف الذي أدخله. يمكن للموظف إضافة ملاحظة خاصة.',
          'قوائم المتابعة: أرقام الشاصي التي تختار متابعتها. تحتوي قوائم الشركاء على أرقام شاصي ووصف يختاره الشريك.',
          'الإشعارات: رسائل داخل التطبيق عن السجلات الجديدة للسيارات التي تتابعها وعن حسابك أو منشأتك.',
          'سجل التدقيق: من قام بماذا ومتى في الإجراءات الحساسة (مثل اعتماد منشأة أو تغيير دور أو حذف حساب)، بما في ذلك البريد الإلكتروني للشخص الذي قام بالإجراء.',
          'السجلات التقنية: تسجّل سجلات الخادم وقت كل طلب والعنوان المطلوب وعنوان IP. كما تحسب حدود تسجيل الدخول عدد الطلبات لكل عنوان IP في الذاكرة لمدة تصل إلى ساعة.',
        ],
        paragraphs: [
          'لا نطلب رقم الهوية الإماراتية أو رقم الهاتف أو العنوان، ولا يسجّل تاريخ السيارة هوية مالكها أبداً.',
        ],
      },
      {
        id: 'why',
        heading: 'لماذا نستخدمها',
        items: [
          'لتشغيل حسابك وإبقائك مسجّل الدخول.',
          'لتمكين المنشآت المعتمدة من إضافة سجلات الصيانة، وعرض هذه السجلات مع اسم المنشأة التي أضافتها.',
          'للتحقق من المنشآت قبل أن تتمكن من إضافة السجلات، باستخدام بيانات رخصتها التجارية ومستنداتها.',
          'لإبلاغك بالسجلات الجديدة للسيارات التي تتابعها.',
          'للحفاظ على أمان سجل: منع تخمين كلمات المرور، والتحقيق في إساءة الاستخدام، والاحتفاظ بسجل تدقيق للتغييرات الحساسة.',
        ],
        paragraphs: ['لا نبيع البيانات، ولا نعرض إعلانات، ولا نستخدم بياناتك في التنميط أو التسويق.'],
      },
      {
        id: 'who-sees-what',
        heading: 'من يرى ماذا',
        items: [
          'يمكن لأي شخص، دون تسجيل الدخول، رؤية تاريخ أي رقم شاصي: الشركة المصنّعة والطراز وسنة الصنع، وتواريخ الخدمة وفئاتها، والأعمال المنجزة، وقراءات العداد، وتحذيرات المسافة، والتصحيحات، واسم المنشأة التي أضافت كل سجل. ويعرض تقرير PDF المعلومات نفسها.',
          'يمكن للشركاء الذين يحملون مفتاح واجهة برمجة من سجل (مثل شركة تأمين تجريبية) قراءة تاريخ المركبة نفسه عبر واجهة الشركاء. ولا يحصلون أبداً على بيانات الحسابات أو الموظفين أو الملاحظات.',
          'يمكن للمنشأة التي أنشأت السجل أن ترى أيضاً اسم الموظف والملاحظة الخاصة، وأن تبحث في سجلاتها وتنزّلها بصيغة CSV أو JSON. ولا تستطيع المنشآت الأخرى ذلك.',
          'يمكن لأعضاء المنشأة رؤية بياناتها وحالتها، ويمكن لمسؤوليها رؤية أعضائها وإدارتهم.',
          'لا يرى مستندات الرخصة إلا مسؤولو المنشأة التي رفعتها ومسؤولو المنصة. ولا يراها المستهلكون أو الشركاء أبداً. ولا يحذفها إلا مسؤول المنصة، ويُسجَّل الحذف.',
          'يمكن لمسؤولي المنصة رؤية الحسابات والمنشآت والأعضاء وجميع سجلات الصيانة (بما فيها أسماء الموظفين والملاحظات الخاصة) وسجل التدقيق لتشغيل المنصة، كما يمكنهم البحث في سجلات الصيانة وتنزيلها. ويُسجَّل كل تنزيل لسجلات الصيانة في سجل التدقيق.',
        ],
      },
      {
        id: 'cookies',
        heading: 'ملفات تعريف الارتباط وتخزين المتصفح',
        paragraphs: ['تستخدم سجل ملفين فقط من ملفات تعريف الارتباط، وكلاهما ضروري للغاية:'],
        items: [
          '«sijil_session»: يبقيك مسجّل الدخول. يحتوي على رمز عشوائي، ولا يمكن لبرامج الصفحة قراءته (HttpOnly)، ولا يُرسل إلا عبر HTTPS، وتنتهي صلاحيته بعد 7 أيام أو عند تسجيل الخروج.',
          '«sijil_csrf»: قيمة عشوائية تحمي النماذج من هجمات تزوير الطلبات عبر المواقع.',
        ],
      },
      {
        id: 'third-parties',
        heading: 'الأطراف الخارجية',
        paragraphs: [
          'تعمل سجل على خوادمها الخاصة بقاعدة بياناتها ومساحة تخزين ملفاتها. لا تحمّل أي نصوص برمجية أو خطوط أو أدوات تحليل أو إعلانات من أطراف خارجية، ولا ترسل أي رسائل بريد إلكتروني.',
          'عند توفر الإنترنت، قد ترسل سجل رقم الشاصي، ورقم الشاصي فقط، إلى خدمة vPIC العامة التابعة للإدارة الوطنية الأمريكية لسلامة المرور على الطرق السريعة، لمعرفة الشركة المصنّعة والطراز وتفاصيل السيارة. ولا يُرسل معه أي شيء عنك. وتعمل سجل دون هذه الخدمة.',
        ],
      },
      {
        id: 'retention',
        heading: 'مدة الاحتفاظ بالبيانات',
        items: [
          'سجلات الصيانة دائمة. تاريخ المركبة يُضاف إليه فقط حتى يكون جديراً بالثقة: يُصحَّح الخطأ بتصحيح مرتبط بالسجل الأصلي، ولا يُعدَّل الأصل أو يُحذف أبداً.',
          'تُحفظ الحسابات حتى حذفها. وتتوقف الجلسات عن العمل بعد 7 أيام كحد أقصى.',
          'عند حذف حساب، تُحذف معه جلساته وعضوياته وقوائم متابعته وإشعاراته. وتبقى سجلات الصيانة التي أدخلها الشخص، ويظهر فيها اسم الموظف كما سُجِّل وقتها. كما تبقى قيود سجل التدقيق، بما فيها البريد الإلكتروني للشخص الذي قام بالإجراء.',
          'عند حذف منشأة، تُحذف معها عضوياتها ومستنداتها، وتبقى سجلات الصيانة الخاصة بها باسمها كما سُجِّل.',
          'تُحفظ مستندات الرخصة ما دامت المنشأة موجودة، ما لم يحذفها مسؤول المنصة قبل ذلك.',
        ],
      },
      {
        id: 'your-choices',
        heading: 'حقوقك وخياراتك',
        items: [
          'الاطلاع على بياناتك: تعرض صفحة ملفك الشخصي بيانات حسابك ودورك وعضوياتك.',
          'تصحيحها: يمكنك تغيير اسمك وكلمة المرور بنفسك. ولتغيير بريدك الإلكتروني، اطلب ذلك من مسؤول المنصة.',
          'حذف حسابك: اطلب ذلك من مسؤول المنصة. وتبقى السجلات التي أدخلتها لصالح منشأة كما هو موضح أعلاه.',
          'الحصول على نسخة: اطلب من مسؤول المنصة نسخة من البيانات المحفوظة عنك.',
        ],
      },
      {
        id: 'security',
        heading: 'كيف نحمي البيانات',
        items: [
          'جميع الاتصالات تستخدم HTTPS.',
          'تُشفَّر كلمات المرور بخوارزمية Argon2id، ولا تُخزَّن رموز الجلسات ومفاتيح واجهة الشركاء إلا في صورة بصمات مشفّرة.',
          'يتحقق الخادم من دورك ومنشأتك في كل إجراء.',
          'محاولات تسجيل الدخول وإنشاء الحسابات محدودة العدد.',
          'تغيير كلمة المرور يُخرجك من جميع الأجهزة الأخرى ويبدأ جلسة جديدة.',
          'تُسجَّل التغييرات الحساسة في سجل التدقيق.',
        ],
        paragraphs: [
          'لا يوجد نظام آمن تماماً. إذا اعتقدت أن حسابك تعرّض لإساءة الاستخدام، فغيّر كلمة المرور وتواصل مع مسؤول المنصة.',
        ],
      },
      {
        id: 'children',
        heading: 'الأطفال',
        paragraphs: ['سجل مخصصة للبالغين الذين يتعاملون مع السيارات والورش، وليست موجّهة للأطفال.'],
      },
      {
        id: 'changes',
        heading: 'التغييرات على هذه السياسة',
        paragraphs: [
          'عندما يتغير ما تخزّنه سجل أو تشاركه، تُحدَّث هذه الصفحة ويتغير تاريخ «آخر تحديث». يُرجى مراجعتها من حين لآخر.',
        ],
      },
      {
        id: 'contact',
        heading: 'التواصل',
        paragraphs: [
          'تُوجَّه الأسئلة أو الطلبات المتعلقة ببياناتك إلى مسؤولي المنصة في نسخة سجل هذه. في النسخة التجريبية لمشروع 42، هم فريق الطلاب الذي بنى سجل، ويمكن التواصل معهم خلال تقييم المشروع.',
        ],
      },
    ],
  },
}
