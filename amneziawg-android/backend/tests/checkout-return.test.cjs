// Regression coverage for the carousel's selected plan surviving browser login.
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const site = readFileSync(join(__dirname, '../app/site_page.py'), 'utf8');
const payment = readFileSync(join(__dirname, '../app/payment_page.py'), 'utf8');
const authFunction = site.slice(site.indexOf('    function setAuth(session)'), site.indexOf('    function clearAuth()'));
const payFunction = payment.slice(payment.indexOf('    function startPayment(channel)'), payment.indexOf('    async function markPaymentDone()'));
function context(plan, token = '') {
  const values = new Map();
  return { values, state: {}, token, selectedPlan: plan, selectedPromotion: null, currentOrder: null,
    sessionStorage: { getItem: k => values.get(k), setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) },
    localStorage: { setItem() {}, removeItem() {} }, location: { href: '' }, renderAuthState() {}, URLSearchParams,
    paymentTarget: () => 'payment-app', setStatus() {}, launchPayment() {}, };
}
for (const planId of ['plan_month', 'plan_quarter', 'plan_year']) {
  const c = context({id: planId}); vm.createContext(c);
  vm.runInContext(payFunction + authFunction, c);
  vm.runInContext('startPayment("alipay")', c);
  assert.equal(c.location.href, '/dashboard');
  assert.equal(c.values.get('xingsui_checkout_plan'), planId);
  vm.runInContext('setAuth({access_token:"test-only",user:{}})', c);
  assert.equal(c.location.href, '/payment?plan_id='+planId);
  assert.equal(c.values.has('xingsui_checkout_plan'), false);
}
const unloaded = context(null); vm.createContext(unloaded); vm.runInContext(payFunction, unloaded);
vm.runInContext('startPayment("wechat")', unloaded); assert.equal(unloaded.location.href, '');
for (const invalid of ['https://example.com', '../admin', '<script>', 'a'.repeat(81), '']) {
  const c = context(null); c.values.set('xingsui_checkout_plan',invalid); vm.createContext(c);
  vm.runInContext(authFunction+'setAuth({access_token:"test-only",user:{}})',c);
  assert.equal(c.location.href,''); assert.equal(c.values.has('xingsui_checkout_plan'),false);
}
const signedIn=context({id:'plan_year'},'test-only');vm.createContext(signedIn);vm.runInContext(payFunction+'startPayment("wechat")',signedIn);
assert.equal(signedIn.location.href,'');
console.log('Checkout return: all plan choices, login return, one-time consumption, invalid input and unloaded state passed.');
