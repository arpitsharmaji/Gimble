"""Copy for the public, crawlable SEO pages (rendered server-side by seo.py).

Written to match Gimble's real policy (friendly, public, NON-sexual company; adults 18+; not a dating or escort service).
Search terms such as "girlfriend on rent" are answered honestly - what Gimble is and is not - never promised as a service.
Do not add claims you cannot back up (prices, user counts, ratings): Google penalises misleading pages and fake review markup.
"""

CTA = "/#/browse"

PAGES: dict[str, dict] = {
    "hire-a-companion": {
        "nav": "Hire a companion",
        "title": "Hire a Companion in India: Safe, Public & Admin-Approved | Gimble",
        "desc": "Want to hire a companion for coffee, a film, a gym session or an event? Gimble is a safety-first marketplace for friendly, public, non-sexual company. 18+ only.",
        "h1": "Hire a companion for the plans you don't want to do alone",
        "kw": ["hire a companion", "hire a companion India", "book a companion", "companionship services", "companion for hire", "hire a partner", "hire a person for company", "social companion"],
        "intro": "Whether you are new to a city, between friend groups, or just want company for an evening, you can hire a companion on Gimble for a time-limited, public plan. Every partner profile is reviewed by our team, every meet-up happens in a public place, and payments stay on the platform.",
        "sections": [
            ("What does it mean to hire a companion?", [
                "A companion is a friendly adult who spends time with you at an agreed activity: a coffee, a film, a museum visit, a workout, a city walk, a dinner or an event. It is company, not a relationship, and it is never sexual.",
                "You choose the activity, the time and a public place. The partner accepts or declines your request, and either of you can end the plan at any time."]),
            ("Plans people book", ["*Coffee and a proper conversation", "*A movie, concert or match buddy", "*A gym, run or yoga partner", "*Exploring a new city or neighbourhood", "*Dinner when you would rather not eat alone", "*A plus-one for a wedding, party or work event", "*A friendly video chat"]),
            ("How hiring a companion on Gimble works", ["#Browse partner profiles and pick someone whose interests match yours.", "#Send a booking request with the activity, time and a public location. A Gimble membership is needed to send requests.", "#Once the partner accepts, you pay through Gimble to confirm the plan.", "#Meet, enjoy the time, and leave a rating afterwards."]),
            ("Safety is built in", ["*Adults 18+ only, with profiles reviewed before they go live", "*Meet-ups in public places only", "*Sexual wording, scams and off-platform payment requests are blocked automatically", "*Report and block tools on every profile and chat", "*In an emergency call 112"]),
        ],
        "faqs": [
            ("Is Gimble an escort or dating service?", "No. Gimble is for friendly, public, non-sexual company. Sexual services, solicitation and adult content are banned, and anyone who breaks that rule is permanently removed."),
            ("Is it safe to hire a companion?", "Meet-ups must be in public places, profiles are reviewed, and chats are screened. You can report or block anyone, and either person can end a plan at any time. Always tell a friend where you are going."),
            ("Do I pay the companion directly?", "No. Payments go through Gimble. Asking you to pay outside the platform breaks our rules, so please report it."),
            ("Who can use Gimble?", "Adults aged 18 and over."),
        ],
        "related": ["rent-a-friend", "event-plus-one", "safe-meeting-tips"],
    },
    "rent-a-friend": {
        "nav": "Rent a friend",
        "title": "Rent a Friend in India: Hire a Friend for Any Plan | Gimble",
        "desc": "Looking to rent a friend or hire a friend for coffee, movies, workouts or a night out? Book friendly, admin-approved company on Gimble. Public meet-ups only.",
        "h1": "Rent a friend: friendly company, whenever you need it",
        "kw": ["rent a friend", "hire a friend", "friend on rent", "rent a friend India", "rental friend", "paid friend", "friend for hire", "activity partner", "lonely"],
        "intro": "Sometimes you just want someone to share a plan with. On Gimble you can rent a friend for an afternoon, a film or a workout: an adult who is there to be good company, in a public place, for as long as you agreed.",
        "sections": [
            ("Why people rent a friend", ["*They moved to a new city for work and do not know anyone yet", "*Long hours left no time to build a social circle", "*Friends are busy and the weekend feels long", "*They want to try something new without going alone", "*They want to practise feeling relaxed around new people"]),
            ("A hired friend and a real friendship", [
                "A hired friend is a time-limited arrangement, and it does not replace the friends you build over years. Many people use it as a low-pressure way to get out of the house, try an activity and warm up to meeting new people.",
                "Some customers and partners do click and rebook each other. Others simply enjoy one good afternoon. Both are fine."]),
            ("Ideas for a first plan", ["*Coffee at a busy cafe", "*A walk through a park or heritage area", "*A film at a mall multiplex", "*A casual lunch", "*A morning workout or yoga class", "*A visit to a museum or bookshop"]),
            ("Keeping it comfortable", ["*Pick a public place you know", "*Tell a friend your plan", "*Keep the first plan short", "*Say if something feels off. You can end the plan at any time and report anything uncomfortable"]),
        ],
        "faqs": [
            ("Can I rent a friend for just one afternoon?", "Yes. Plans are time-limited and you choose the duration when you send your request."),
            ("Will a rented friend be a romantic partner?", "No. Gimble is friendly, platonic company only. Romantic or sexual arrangements are not allowed."),
            ("What if I feel uncomfortable?", "End the plan whenever you like and use the report button. Our team reviews every report."),
        ],
        "related": ["meet-new-people", "hire-a-companion", "safe-meeting-tips"],
    },
    "partner-on-rent": {
        "nav": "Girlfriend / boyfriend / partner on rent",
        "title": "Girlfriend, Boyfriend or Partner on Rent in India? | Gimble",
        "desc": "Searching for a girlfriend, boyfriend or partner on rent? Here is what is real, what is not, and how to hire a friendly partner for public plans on Gimble.",
        "h1": "Girlfriend on rent, boyfriend on rent, partner on rent: what you should know",
        "kw": ["girlfriend on rent", "boyfriend on rent", "partner on rent", "rent a girlfriend", "rent a boyfriend", "hire a partner", "hire a girlfriend", "hire a boyfriend", "partner for hire"],
        "intro": "People search for a \"girlfriend on rent\", \"boyfriend on rent\" or \"partner on rent\" for many reasons: loneliness, a family event, pressure to turn up with someone, or simply wanting company. Here is an honest explanation of what Gimble offers. On Gimble you can hire a partner for friendly, public, platonic plans. We do not offer romantic relationships, sexual services, escort services or any kind of paid dating.",
        "sections": [
            ("What \"partner\" means on Gimble", ["On Gimble a partner is an adult who offers friendly company for an activity: coffee, a film, a workout, a walk, dinner or an event. The word describes the role in a booking, not a relationship."]),
            ("What you can hire a partner for", ["*A plus-one for a wedding, sangeet, reunion or office party", "*Company for dinner, a film or a concert", "*Someone to explore the city with", "*A friendly person to practise conversation with before a big social event"]),
            ("What Gimble does not do", ["*No romantic or pretend-relationship arrangements", "*No sexual services, escort or adult services", "*No private-place meetings: public places only", "*No payments outside the platform"]),
            ("Be careful with other offers", ["Sites and social media accounts that promise a girlfriend or boyfriend on rent often ask for an advance payment to a personal UPI ID or WhatsApp number. That is a common scam pattern.", "Never send money to a personal account for a booking. On Gimble payments are made through the platform, and asking you to pay elsewhere is a reason to report the profile."]),
            ("If you are looking for a relationship", ["Gimble is not a dating or matchmaking service. For romance, consider meeting people through hobby groups, classes, friends of friends or a dedicated dating app, and use the safety steps in our guide to meeting someone new."]),
        ],
        "faqs": [
            ("Can I get a girlfriend or boyfriend on rent through Gimble?", "No. Gimble partners offer friendly, platonic company for public plans. Romantic relationships and sexual services are not offered and are banned on the platform."),
            ("Can I hire a partner to come to a wedding or party with me?", "Yes, as a friendly plus-one at a public or event venue. Introduce them as a friend and agree the time and plan in advance."),
            ("Is it safe to hire a partner on Gimble?", "Profiles are reviewed, chats are screened, meet-ups are in public places and payments stay on the platform. You can report or block anyone."),
            ("Why do some websites promise more than this?", "We cannot speak for other sites, but we hold to one rule: friendly, public, non-sexual company only."),
        ],
        "related": ["event-plus-one", "hire-a-companion", "blind-date-alternative"],
    },
    "blind-date-alternative": {
        "nav": "Blind date & meeting new people safely",
        "title": "Nervous About a Blind Date? Meet New People Safely | Gimble",
        "desc": "Nervous about a blind date or meeting someone new? Safety steps for a first meeting, plus how a friendly companion on Gimble can help you warm up socially.",
        "h1": "Blind date jitters? How to meet new people with confidence",
        "kw": ["blind date", "blind date tips", "first date safety", "meet new people", "meeting a stranger safely", "date night company", "social confidence"],
        "intro": "A blind date or a first meeting with someone you found online can feel exciting and nerve-wracking at the same time. These steps keep you safe, and they work for any first meeting, whether it is a date, a friendship or a work contact.",
        "sections": [
            ("Before you meet", ["*Choose a busy public place and a daytime or early-evening slot", "*Tell a friend who you are meeting, where and when", "*Do a short video call first so there are no surprises", "*Arrange your own transport both ways", "*Keep payments and personal details to yourself until you trust the person"]),
            ("During the meeting", ["*Keep your phone charged and your drink in sight", "*Share your live location with a friend", "*You never owe anyone more time. Leave if something feels wrong", "*Skip private spaces such as a flat or hotel room"]),
            ("Where Gimble fits", ["Gimble is not a dating or matchmaking service, and it does not arrange blind dates. Some people do use it to warm up socially: a relaxed coffee with a friendly companion is a low-pressure way to practise small talk and feel at ease in a cafe or restaurant.", "That is company for a public, platonic plan. Nothing more is offered or allowed."]),
            ("Other ways to meet new people", ["*Join a running, cycling or book club", "*Take a class: cooking, dance, photography, a language", "*Volunteer for a cause you care about", "*Try coworking spaces and community events"]),
        ],
        "faqs": [
            ("Does Gimble arrange blind dates?", "No. Gimble is for friendly, public, non-sexual company and is not a dating service."),
            ("How do I stay safe on a first date with a stranger?", "Meet in a busy public place, tell a friend your plan, share your location, arrange your own transport and leave if you feel uncomfortable."),
            ("How can I feel less nervous about meeting new people?", "Start with short, low-pressure plans in familiar places, such as a coffee or a walk, and build up from there."),
        ],
        "related": ["safe-meeting-tips", "meet-new-people", "partner-on-rent"],
    },
    "event-plus-one": {
        "nav": "Plus-one for events",
        "title": "Hire a Plus-One for Weddings, Parties & Events | Gimble",
        "desc": "Need someone to go with you to a wedding, party, reunion or work event? Hire a friendly plus-one on Gimble: admin-approved partners, public venues, safe payments.",
        "h1": "Hire a plus-one for the event you would rather not attend alone",
        "kw": ["plus one for wedding", "hire a plus one", "wedding date", "event companion", "party companion", "hire a partner for events", "wedding guest companion", "corporate event companion"],
        "intro": "Weddings, reunions and office parties are easier with a friendly face beside you. On Gimble you can book a plus-one: an adult who joins you at a public or event venue as good company, for the time you agreed.",
        "sections": [
            ("Events where people bring a plus-one", ["*Weddings, sangeets and receptions", "*Family functions and festivals", "*Office parties and networking evenings", "*College or school reunions", "*Concerts, screenings and gallery openings"]),
            ("Making it go smoothly", ["*Share the dress code, timings and venue address in your request", "*Agree in advance how you will introduce each other. A friend is simplest", "*Book early so you can chat on Gimble before the day", "*Plan how you will get home, and tell a friend where you are"]),
            ("What a plus-one is on Gimble", ["A plus-one is friendly, platonic company at a public or event venue. It is not a romantic arrangement, and Gimble does not allow sexual services, off-platform payments or meetings in private places."]),
        ],
        "faqs": [
            ("Can I hire a plus-one for a wedding?", "Yes. Send a booking request with the venue and timings. The partner can accept or decline."),
            ("How far ahead should I book?", "As early as you can. Partners accept requests based on their availability, and you also need time to chat beforehand."),
            ("Can the plus-one pretend to be my partner?", "We recommend introducing them as a friend. Gimble partners offer friendly company, not a staged relationship."),
        ],
        "related": ["partner-on-rent", "hire-a-companion", "safe-meeting-tips"],
    },
    "meet-new-people": {
        "nav": "Meet new people",
        "title": "How to Meet New People in a New City | Gimble",
        "desc": "Moved to a new city and want to meet new people? Practical ideas for making friends as an adult, plus how a friendly companion on Gimble can help you get started.",
        "h1": "How to meet new people when you do not know anyone",
        "kw": ["meet new people", "make friends as an adult", "new city friends", "feeling lonely", "activity partner", "workout buddy", "movie buddy", "find a friend"],
        "intro": "Making friends as an adult takes effort, especially after a move or a job change. Here are practical ways to meet new people, and where a friendly companion from Gimble can help you take the first step.",
        "sections": [
            ("Why it feels harder as an adult", ["Work takes most of the day, friend groups are already formed and there is no built-in setting like school or college. The fix is to create regular, repeatable contact with the same people."]),
            ("Eight ways to meet new people", ["#Join a club around something you already enjoy: running, football, chess, books", "#Take an evening class", "#Volunteer on a regular schedule", "#Go to the same cafe or gym at the same time each week", "#Say yes to invitations, even small ones", "#Use a coworking space or community events", "#Follow up within a few days of meeting someone", "#Host something small, such as a film night or a walk"]),
            ("Where hiring a companion helps", ["Going somewhere new alone is the hardest part. A booking on Gimble gives you someone friendly to explore a cafe, a market or a gym class with, so the next visit feels less intimidating. It is public, platonic company for a plan you choose."]),
            ("Make it stick", ["*Repeat plans so they become routine", "*Invite people you meet to the same activity", "*Give friendships time. Most take several meetings"]),
        ],
        "faqs": [
            ("How can I make friends in a new city?", "Join recurring activities, say yes to invitations and follow up. A friendly companion on Gimble can also help you try places and activities you would hesitate to visit alone."),
            ("Is it normal to feel lonely after moving?", "Yes, it is very common and usually improves as you build routines and a few regular contacts."),
        ],
        "related": ["rent-a-friend", "hire-a-companion", "blind-date-alternative"],
    },
    "safe-meeting-tips": {
        "nav": "Safety tips",
        "title": "Safety Tips for Meeting Someone New in India | Gimble",
        "desc": "Practical safety tips for meeting someone new: choose public places, share your plan, keep payments on-platform, spot red flags and know who to call.",
        "h1": "Safety tips for meeting someone you have just met online",
        "kw": ["safety tips meeting stranger", "online meeting safety", "first meeting safety", "avoid scams", "red flags", "women safety tips"],
        "intro": "Most meetings go well, and a few simple habits make them safer. These tips apply on Gimble and anywhere else you meet someone new.",
        "sections": [
            ("Before you go", ["*Meet in a busy public place, in daylight or early evening", "*Tell a friend who, where and when", "*Chat on the platform first and keep your phone number and address private", "*Arrange your own transport"]),
            ("Red flags", ["*Asking for money, gifts or an advance payment", "*Asking you to pay a personal UPI ID or move to WhatsApp early on", "*Pushing to meet somewhere private", "*Sexual comments or pressure", "*Stories that change or do not add up"]),
            ("If something feels wrong", ["*Leave. You never owe anyone more time", "*Go to a crowded place and call a friend", "*In an emergency call 112. In India the women's helpline is 1091", "*Report the profile to Gimble with screenshots so we can act"]),
        ],
        "faqs": [
            ("What should I do if someone asks me to pay outside the platform?", "Do not pay. Stop replying and report the profile. Off-platform payment requests are against Gimble's rules."),
            ("Which number do I call in an emergency in India?", "Call 112. The women's helpline is 1091."),
        ],
        "related": ["hire-a-companion", "blind-date-alternative", "partner-on-rent"],
    },
}

# slug -> (display name, well-known public areas used for first meet-ups)
CITIES: dict[str, tuple[str, list[str]]] = {
    "gurugram": ("Gurugram", ["CyberHub", "Galleria Market", "Sector 29", "Golf Course Road cafes"]),
    "delhi": ("Delhi", ["Connaught Place", "Hauz Khas Village", "Khan Market", "Select Citywalk, Saket"]),
    "noida": ("Noida", ["Sector 18", "DLF Mall of India", "Okhla Bird Sanctuary"]),
    "mumbai": ("Mumbai", ["Carter Road, Bandra", "Colaba Causeway", "Marine Drive", "Phoenix Palladium, Lower Parel"]),
    "bengaluru": ("Bengaluru", ["Indiranagar", "Church Street", "Cubbon Park", "Koramangala"]),
    "hyderabad": ("Hyderabad", ["Banjara Hills", "Jubilee Hills", "Necklace Road", "Inorbit Mall, HITEC City"]),
    "pune": ("Pune", ["Koregaon Park", "FC Road", "Phoenix Marketcity, Viman Nagar"]),
}
