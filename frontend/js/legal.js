import { html, raw } from './core.js';

const DRAFT = '<div class="notice warn"><b>Draft template - not legal advice.</b> Have a qualified Indian lawyer review and finalise this text (DPDP Act 2023, IT Act, consumer, tax and payments rules) before public launch.</div>';

const PAGES = {
  safety: ['Safety centre', `
    <div class="notice"><b>In danger? Call 112.</b> Women's helpline <a href="tel:1091">1091</a> · Cyber-crime helpline <a href="tel:1930">1930</a></div>
    <h2>Before you meet</h2><ul><li>Always meet in a busy public place - a café, restaurant, mall or event. Never a private home, hotel room or vehicle.</li><li>Tell a friend or family member who you're meeting, where and when. Share your live location with them.</li><li>Keep all chats in PairUp until you've met. Don't share your home address, workplace or OTPs.</li><li>Arrange your own transport so you can leave whenever you want.</li></ul>
    <h2>Money</h2><ul><li>Pay only through PairUp. Anyone asking for UPI transfers, wallet payments, advance fees or gift cards is likely running a scam - report them.</li><li>PairUp staff will never ask for your password or OTP.</li></ul>
    <h2>Boundaries</h2><ul><li>PairUp is for friendly, non-sexual company. Sexual or adult-service requests are banned and lead to permanent removal.</li><li>"No" means no. Either person can end the plan at any time.</li></ul>
    <h2>Report &amp; block</h2><p>Use <b>Report</b> or <b>Block</b> on any profile or chat. During a booking, the <b>🛡 Safety</b> button alerts our team. Profiles reported by several people are automatically hidden pending review.</p>`],
  terms: ['Terms of Service', DRAFT + `
    <h2>1. What PairUp is</h2><p>PairUp is an online platform where adults (18+) can discover and arrange time-limited, public, non-sexual companionship for activities such as coffee, films, fitness and city exploration. PairUp is a marketplace; partners are independent individuals, not employees or agents of PairUp.</p>
    <h2>2. Eligibility</h2><p>You must be at least 18 and legally able to enter a contract. You must give accurate details.</p>
    <h2>3. Prohibited conduct</h2><p>Sexual services or solicitation, escort or adult services, harassment, discrimination, impersonation, collecting money outside PairUp, illegal activity, sharing others' private information, and any content involving minors. Violations lead to removal and may be reported to authorities.</p>
    <h2>4. Memberships &amp; payments</h2><p>Customers pay a membership fee to send booking requests. Fees, taxes, cancellation and refund terms: <i>[to be completed with your payment provider and legal adviser]</i>.</p>
    <h2>5. Bookings</h2><p>A booking is a request until the partner accepts. Either party may cancel with a reason. Meetings must take place in public venues.</p>
    <h2>6. Liability</h2><p><i>[Limitation of liability, indemnity, dispute resolution and governing law - to be drafted by counsel.]</i></p>`],
  privacy: ['Privacy Policy', DRAFT + `
    <h2>Data we collect</h2><p>Name, email, date of birth, city, optional gender, profile content and photos (partners), bookings, messages, reports, and basic technical data. Photos are re-encoded on upload and location metadata is stripped.</p>
    <h2>How we use it</h2><p>To run the marketplace, verify eligibility (18+), keep users safe, prevent fraud and meet legal obligations.</p>
    <h2>Sharing</h2><p>Partners see a customer's first name and booking details; customers see partner profiles you publish. Payments are processed by our payment provider. We don't sell personal data.</p>
    <h2>Your choices</h2><p>You can edit your profile, block users, change your password and delete your account from Account. <i>[Grievance officer, retention periods and cross-border transfer details to be completed.]</i></p>`],
  standards: ['Community Standards', `
    <h2>Be respectful</h2><p>Treat everyone with courtesy. No harassment, hate, threats or pressure.</p>
    <h2>Keep it non-sexual and public</h2><p>No sexual content, innuendo or adult-service offers - in profiles, photos, chats or booking notes. Meet only in public places.</p>
    <h2>Be honest</h2><p>Use your own real photos and details. Show up on time or cancel early.</p>
    <h2>Keep payments on PairUp</h2><p>Never ask for or send money outside the platform.</p>
    <h2>Consequences</h2><p>Warnings, profile removal, suspension, and referral to law enforcement where required.</p>`],
};

export function legalPage(root, key) {
  const [title, body] = PAGES[key] || PAGES.safety;
  root.innerHTML = html`<div class="page narrow legal"><h1>${title}</h1>${raw(body)}<p class="muted small">Related: <a href="#/safety">Safety</a> · <a href="#/terms">Terms</a> · <a href="#/privacy">Privacy</a> · <a href="#/standards">Community Standards</a></p></div>`.s;
}
