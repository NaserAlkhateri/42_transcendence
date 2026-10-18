// Terms of Service (NA-07). Keep in step with how Sijil works; see the note in privacy.ts.

import { LEGAL_UPDATED, type BilingualDocument } from './types'

export const TERMS_OF_SERVICE: BilingualDocument = {
  en: {
    title: 'Terms of Service',
    updated: LEGAL_UPDATED.en,
    intro: [
      'These terms apply to everyone who uses Sijil: people looking up a car, workshops and dealerships that record services, partners using the partner API, and platform admins. By using Sijil or creating an account you agree to them. Read them together with the Privacy Policy.',
    ],
    sections: [
      {
        id: 'demo',
        heading: 'Sijil is a demo',
        paragraphs: [
          'Sijil is a student project built for the 42 curriculum to show how a trustworthy vehicle service history could work in the UAE. It is not an official record and is not connected to the RTA, the police, any government body, insurer or dealer. Its data is fictional or entered by demo users.',
          'Don’t rely on Sijil alone to buy, sell, insure or value a car. Always have the car inspected and check official documents such as the Mulkiya (vehicle registration card).',
        ],
      },
      {
        id: 'accounts',
        heading: 'Your account',
        items: [
          'Give a real name and an email address you control. One account is for one person.',
          'Keep your password secret and don’t share your account. If you received a temporary password, you must choose your own before using Sijil.',
          'Tell a platform admin if you think someone else has used your account.',
          'Anyone can create a consumer account. Business roles are given only through an approved workshop or dealership, and platform roles only by platform admins.',
        ],
      },
      {
        id: 'history',
        heading: 'Vehicle history and its limits',
        items: [
          'A record shows what an approved business reported. Approval means a platform admin checked the business’s trade licence before it could add records. It does not guarantee that every record is true or complete.',
          'Mileage warnings mean a reading didn’t fit the earlier history (for example, the odometer went down). A warning is a signal to ask questions, not proof of fraud.',
          'History is permanent. Records are never edited or deleted; a mistake is fixed by a linked correction, and both stay visible.',
          'A VIN with no history only means no approved business has recorded a service for it on Sijil.',
        ],
      },
      {
        id: 'businesses',
        heading: 'Workshops and dealerships',
        items: [
          'Register only a business you are entitled to represent, with its real trade licence. A platform admin may approve, reject or later withdraw approval.',
          'Add only services your business actually performed, with the correct date, work done and odometer reading as shown on the car.',
          'Correct your own mistakes with a correction. Never use a record to hide or alter another business’s history.',
          'Keep private notes to what the job needs. Don’t write customers’ names, phone numbers or other personal details in them.',
          'Entity admins are responsible for who they add as members and staff, and should remove people who leave.',
          'False or misleading records may lead to approval being withdrawn and accounts being disabled or deleted. The records themselves stay, because history is permanent.',
        ],
      },
      {
        id: 'partners',
        heading: 'Partner API',
        items: [
          'API keys are issued by platform admins to named partners. Keep your key secret, use it only on your own servers and ask for it to be revoked if it leaks.',
          'Keys are read-only for vehicle history. Your watchlist is yours to manage.',
          'Respect the rate limits. Don’t try to copy the whole database or get around the limits with extra keys.',
          'Don’t put your customers’ personal data, such as names, in watch labels. Use your own reference numbers.',
          'Show Sijil data to your users as what it is: demo service history reported by businesses, not an official record.',
          'A key can be revoked at any time, for example after misuse.',
        ],
      },
      {
        id: 'acceptable-use',
        heading: 'Acceptable use',
        paragraphs: ['You must not:'],
        items: [
          'try to break into accounts, guess passwords or get around rate limits or permission checks;',
          'access another organisation’s data or act for a business you don’t belong to;',
          'impersonate another person, business, government body or brand;',
          'upload malicious files, or documents you have no right to share;',
          'disrupt Sijil, or scrape it in bulk outside the partner API.',
        ],
      },
      {
        id: 'documents',
        heading: 'Documents you upload',
        paragraphs: [
          'When a business uploads its trade licence or similar documents, it confirms it may share them for verification. They are stored privately and seen only by that business’s entity admins and Sijil’s platform admins. Only a platform admin can delete them, and every deletion is recorded.',
        ],
      },
      {
        id: 'ending',
        heading: 'Suspension and closing accounts',
        paragraphs: [
          'Platform admins may disable or delete accounts, withdraw a business’s approval or revoke API keys if these terms are broken or to protect other users. You can ask a platform admin to delete your account at any time. What happens to your data then is explained in the Privacy Policy.',
        ],
      },
      {
        id: 'no-warranty',
        heading: 'No warranty',
        paragraphs: [
          'Sijil is provided as it is, for demonstration. It may be unavailable, change or lose data, and it comes with no warranty that it is accurate, complete or fit for any purpose. As far as the law allows, the team that built and runs it is not liable for decisions made using it.',
        ],
      },
      {
        id: 'changes',
        heading: 'Changes to these terms',
        paragraphs: [
          'These terms may change as Sijil changes. The date at the top shows the latest version. Continuing to use Sijil after a change means you accept the new terms.',
        ],
      },
      {
        id: 'contact',
        heading: 'Contact',
        paragraphs: [
          'Questions about these terms go to the platform admins of this Sijil deployment. For the 42 demo, that is the student team that built Sijil.',
        ],
      },
    ],
  },

  ar: {
    title: 'شروط الخدمة',
    updated: LEGAL_UPDATED.ar,
    intro: [
      'تنطبق هذه الشروط على كل من يستخدم سجل: من يبحث عن تاريخ سيارة، والورش والوكالات التي تسجّل الخدمات، والشركاء الذين يستخدمون واجهة الشركاء، ومسؤولي المنصة. باستخدامك سجل أو إنشائك حساباً فيها فإنك توافق على هذه الشروط. اقرأها مع سياسة الخصوصية.',
    ],
    sections: [
      {
        id: 'demo',
        heading: 'سجل نسخة تجريبية',
        paragraphs: [
          'سجل مشروع طلابي أُنشئ ضمن منهج 42 لعرض كيف يمكن أن يعمل سجل موثوق لصيانة المركبات في الإمارات. وهو ليس سجلاً رسمياً، وغير مرتبط بهيئة الطرق والمواصلات أو الشرطة أو أي جهة حكومية أو شركة تأمين أو وكالة. بياناته خيالية أو أدخلها مستخدمون تجريبيون.',
          'لا تعتمد على سجل وحده لشراء سيارة أو بيعها أو تأمينها أو تقييمها. افحص السيارة دائماً وتحقق من المستندات الرسمية مثل الملكية.',
        ],
      },
      {
        id: 'accounts',
        heading: 'حسابك',
        items: [
          'استخدم اسمك الحقيقي وبريداً إلكترونياً تملكه. الحساب الواحد لشخص واحد.',
          'حافظ على سرية كلمة المرور ولا تشارك حسابك. إذا حصلت على كلمة مرور مؤقتة، فعليك اختيار كلمة مرور خاصة بك قبل استخدام سجل.',
          'أبلغ مسؤول المنصة إذا اعتقدت أن شخصاً آخر استخدم حسابك.',
          'يمكن لأي شخص إنشاء حساب مستهلك. أما أدوار المنشآت فلا تُمنح إلا عبر ورشة أو وكالة معتمدة، وأدوار المنصة لا يمنحها إلا مسؤولو المنصة.',
        ],
      },
      {
        id: 'history',
        heading: 'تاريخ المركبة وحدوده',
        items: [
          'يعرض السجل ما أبلغت عنه منشأة معتمدة. ويعني الاعتماد أن مسؤول المنصة تحقق من الرخصة التجارية للمنشأة قبل أن تتمكن من إضافة السجلات، ولا يضمن أن كل سجل صحيح أو كامل.',
          'تحذيرات المسافة تعني أن قراءة ما لا تتوافق مع التاريخ السابق (مثلاً انخفاض قراءة العداد). والتحذير إشارة لطرح الأسئلة، وليس دليلاً على الاحتيال.',
          'التاريخ دائم. لا تُعدَّل السجلات ولا تُحذف أبداً، ويُصحَّح الخطأ بتصحيح مرتبط بالسجل الأصلي، ويبقى الاثنان ظاهرين.',
          'رقم الشاصي الذي لا تاريخ له يعني فقط أن أي منشأة معتمدة لم تسجّل له خدمة على سجل.',
        ],
      },
      {
        id: 'businesses',
        heading: 'الورش والوكالات',
        items: [
          'لا تسجّل إلا منشأة يحق لك تمثيلها، برخصتها التجارية الحقيقية. ويجوز لمسؤول المنصة اعتمادها أو رفضها أو سحب اعتمادها لاحقاً.',
          'لا تُضف إلا الخدمات التي نفّذتها منشأتك فعلاً، بالتاريخ الصحيح والأعمال المنجزة وقراءة العداد كما تظهر في السيارة.',
          'صحّح أخطاءك بتصحيح مرتبط. ولا تستخدم أي سجل لإخفاء تاريخ منشأة أخرى أو تغييره.',
          'اقصر الملاحظات الخاصة على ما يحتاجه العمل. ولا تكتب فيها أسماء العملاء أو أرقام هواتفهم أو أي بيانات شخصية أخرى.',
          'مسؤولو المنشأة مسؤولون عمّن يضيفونهم أعضاءً وموظفين، وعليهم إزالة من يغادر.',
          'قد تؤدي السجلات الكاذبة أو المضللة إلى سحب الاعتماد وتعطيل الحسابات أو حذفها. وتبقى السجلات نفسها لأن التاريخ دائم.',
        ],
      },
      {
        id: 'partners',
        heading: 'واجهة الشركاء',
        items: [
          'يصدر مسؤولو المنصة مفاتيح واجهة البرمجة لشركاء محددين بالاسم. حافظ على سرية مفتاحك، واستخدمه على خوادمك فقط، واطلب إلغاءه إذا تسرّب.',
          'المفاتيح للقراءة فقط بالنسبة لتاريخ المركبات. أما قائمة المتابعة فتديرها بنفسك.',
          'التزم بحدود عدد الطلبات. ولا تحاول نسخ قاعدة البيانات كاملة أو تجاوز الحدود بمفاتيح إضافية.',
          'لا تضع البيانات الشخصية لعملائك، مثل الأسماء، في أوصاف المتابعة. استخدم أرقامك المرجعية الخاصة.',
          'اعرض بيانات سجل لمستخدميك على حقيقتها: تاريخ صيانة تجريبي أبلغت عنه منشآت، وليس سجلاً رسمياً.',
          'يمكن إلغاء المفتاح في أي وقت، مثلاً بعد إساءة استخدامه.',
        ],
      },
      {
        id: 'acceptable-use',
        heading: 'الاستخدام المقبول',
        paragraphs: ['يُحظر عليك:'],
        items: [
          'محاولة اختراق الحسابات أو تخمين كلمات المرور أو تجاوز حدود الطلبات أو فحوصات الصلاحيات؛',
          'الوصول إلى بيانات منشأة أخرى أو التصرف باسم منشأة لا تنتمي إليها؛',
          'انتحال شخصية شخص أو منشأة أو جهة حكومية أو علامة تجارية؛',
          'رفع ملفات ضارة أو مستندات لا يحق لك مشاركتها؛',
          'تعطيل سجل أو جمع بياناتها بكميات كبيرة خارج واجهة الشركاء.',
        ],
      },
      {
        id: 'documents',
        heading: 'المستندات التي ترفعها',
        paragraphs: [
          'عندما ترفع منشأة رخصتها التجارية أو مستندات مشابهة، فإنها تؤكد أنه يحق لها مشاركتها لغرض التحقق. تُخزَّن هذه المستندات بشكل خاص، ولا يراها إلا مسؤولو تلك المنشأة ومسؤولو المنصة في سجل. ولا يحذفها إلا مسؤول المنصة، ويُسجَّل كل حذف.',
        ],
      },
      {
        id: 'ending',
        heading: 'الإيقاف وإغلاق الحسابات',
        paragraphs: [
          'يجوز لمسؤولي المنصة تعطيل الحسابات أو حذفها، أو سحب اعتماد منشأة، أو إلغاء مفاتيح واجهة البرمجة، إذا خُولفت هذه الشروط أو لحماية المستخدمين الآخرين. ويمكنك أن تطلب من مسؤول المنصة حذف حسابك في أي وقت، وتوضح سياسة الخصوصية ما يحدث لبياناتك عندها.',
        ],
      },
      {
        id: 'no-warranty',
        heading: 'إخلاء المسؤولية',
        paragraphs: [
          'تُقدَّم سجل كما هي، لأغراض العرض. وقد تكون غير متاحة، أو تتغير، أو تفقد بيانات، ولا يوجد أي ضمان بأنها دقيقة أو كاملة أو مناسبة لأي غرض. وبالقدر الذي يسمح به القانون، لا يتحمل الفريق الذي بناها ويشغّلها مسؤولية القرارات المتخذة بناءً عليها.',
        ],
      },
      {
        id: 'changes',
        heading: 'التغييرات على هذه الشروط',
        paragraphs: [
          'قد تتغير هذه الشروط مع تغير سجل. ويوضح التاريخ في أعلى الصفحة أحدث نسخة. واستمرارك في استخدام سجل بعد أي تغيير يعني قبولك الشروط الجديدة.',
        ],
      },
      {
        id: 'contact',
        heading: 'التواصل',
        paragraphs: [
          'تُوجَّه الأسئلة المتعلقة بهذه الشروط إلى مسؤولي المنصة في نسخة سجل هذه. في النسخة التجريبية لمشروع 42، هم فريق الطلاب الذي بنى سجل.',
        ],
      },
    ],
  },
}
