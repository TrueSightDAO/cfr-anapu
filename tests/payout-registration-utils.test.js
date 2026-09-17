/**
 * Unit tests for payout-registration-utils.js
 * Run: node tests/payout-registration-utils.test.js
 *
 * The privacy-critical assertions are:
 *   - a raw PIX key NEVER appears in buildRedactedSummary() output
 *   - maskPixKey() never leaks more than the trailing 1-4 chars
 *
 * The identity-contract assertions are:
 *   - pkHashFromSha256() matches the DAO's 'pk-' + base64url(sha256)[:12] shape
 *     (checked against Node's independent base64url oracle -- no key fixture)
 *   - the payload is minimal (pk_hash + pix_key + program only)
 */
const assert = require('assert');
const crypto = require('crypto');
const u = require('../payout-registration-utils.js');

let passed = 0, failed = 0;
const queue = [];
function test(name, fn) { queue.push([name, fn]); }

// --- CPF -------------------------------------------------------------------
test('isValidCpf accepts a valid CPF (dotted)', () => {
    assert.strictEqual(u.isValidCpf('111.444.777-35'), true);
});
test('isValidCpf rejects bad check digits', () => {
    assert.strictEqual(u.isValidCpf('111.444.777-36'), false);
});
test('isValidCpf rejects all-same-digit', () => {
    assert.strictEqual(u.isValidCpf('11111111111'), false);
});
test('isValidCpf rejects wrong length', () => {
    assert.strictEqual(u.isValidCpf('123456789'), false);
});

// --- CNPJ ------------------------------------------------------------------
test('isValidCnpj accepts a valid CNPJ', () => {
    assert.strictEqual(u.isValidCnpj('11.222.333/0001-81'), true);
});
test('isValidCnpj rejects bad check digits', () => {
    assert.strictEqual(u.isValidCnpj('11.222.333/0001-82'), false);
});

// --- email / phone / EVP ---------------------------------------------------
test('isValidEmail basic', () => {
    assert.strictEqual(u.isValidEmail('maria@example.com'), true);
    assert.strictEqual(u.isValidEmail('nope'), false);
});
test('isValidPhone requires country-code signal', () => {
    assert.strictEqual(u.isValidPhone('+55 11 99999-8888'), true);
    assert.strictEqual(u.isValidPhone('999998888'), false);      // bare 9 -> ambiguous
    assert.strictEqual(u.isValidPhone('5511999998888'), true);   // 13 digits
});
test('isEvp recognises a 32-hex random key', () => {
    assert.strictEqual(u.isEvp('123e4567-e89b-12d3-a456-426614174000'), true);
    assert.strictEqual(u.isEvp('deadbeefdeadbeefdeadbeefdeadbeef'), true);
    assert.strictEqual(u.isEvp('not-a-key'), false);
});

// --- detection -------------------------------------------------------------
test('detectPixKeyType classifies each shape', () => {
    assert.strictEqual(u.detectPixKeyType('111.444.777-35'), 'CPF');
    assert.strictEqual(u.detectPixKeyType('11.222.333/0001-81'), 'CNPJ');
    assert.strictEqual(u.detectPixKeyType('a@b.com'), 'EMAIL');
    assert.strictEqual(u.detectPixKeyType('+5511999998888'), 'PHONE');
    assert.strictEqual(u.detectPixKeyType('deadbeefdeadbeefdeadbeefdeadbeef'), 'EVP');
});

// --- validation ------------------------------------------------------------
test('validatePixKey returns {valid,type,reason}', () => {
    const ok = u.validatePixKey('111.444.777-35');
    assert.strictEqual(ok.valid, true);
    assert.strictEqual(ok.type, 'CPF');
    const bad = u.validatePixKey('111.444.777-36');
    assert.strictEqual(bad.valid, false);
    assert.ok(bad.reason);
});
test('validatePixKey flags empty', () => {
    assert.strictEqual(u.validatePixKey('').valid, false);
});

// --- masking (privacy) -----------------------------------------------------
test('maskPixKey CPF leaks only last 2 digits', () => {
    const m = u.maskPixKey('111.444.777-35');
    assert.strictEqual(m, '***.***.***-35');
    assert.ok(!m.includes('444'));
});
test('maskPixKey email keeps only 1st char + domain', () => {
    const m = u.maskPixKey('maria@example.com');
    assert.strictEqual(m, 'm***@example.com');
    assert.ok(!m.includes('aria'));
});
test('maskPixKey phone leaks only last 4', () => {
    assert.strictEqual(u.maskPixKey('+5511999998888'), '****8888');
});

// --- pk_hash (identity) ----------------------------------------------------
test('pkHashFromSha256 formats as pk-<12> base64url (matches DAO convention)', () => {
    // Hardcoded digest double -- no keypair needed. Node's base64url is the
    // independent oracle for the alphabet/truncation rule.
    const bytes = new Uint8Array(32);
    for (let i = 0; i < 32; i++) bytes[i] = i * 7 % 256;
    const h = u.pkHashFromSha256(bytes);
    const ref = Buffer.from(bytes).toString('base64url').slice(0, 12);
    assert.strictEqual(h, 'pk-' + ref);
    assert.strictEqual(h.length, 15);
    assert.strictEqual(u.isValidPkHash(h), true);
});
test('derivePkHash sha256s the decoded SPKI bytes (async)', async () => {
    // Any bytes work -- derivePkHash hashes what it is given without validating
    // it is a real key, so a tiny deterministic double suffices here.
    const der = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const b64 = Buffer.from(der).toString('base64');
    const h = await u.derivePkHash(b64);
    const ref = 'pk-' + crypto.createHash('sha256').update(Buffer.from(der)).digest('base64url').slice(0, 12);
    assert.strictEqual(h, ref);
});
test('derivePkHash returns empty for no key', async () => {
    assert.strictEqual(await u.derivePkHash(''), '');
});
test('maskPkHash keeps head + tail only', () => {
    assert.strictEqual(u.maskPkHash('pk-abcdef123456'), 'pk-abcd… 3456'.replace(' ', ''));
    assert.strictEqual(u.maskPkHash(''), '');
});

// --- payload split (the core contract) -------------------------------------
test('buildPayoutRegistrationPayload is minimal: pk_hash + pix_key + program', () => {
    const p = u.buildPayoutRegistrationPayload({
        pkHash: 'pk-abcdef123456', programSlug: 'crf-anapu', pixKey: '111.444.777-35',
        submissionSource: 'https://cfr.truesight.me/payout_registration.html'
    });
    assert.strictEqual(p.pix_key, '111.444.777-35');
    assert.strictEqual(p.pix_key_type, 'CPF');
    assert.strictEqual(p.pk_hash, 'pk-abcdef123456');
    assert.strictEqual(p.program_slug, 'crf-anapu');
    assert.strictEqual(p.has_key, true);
    // The redundant identity fields are gone from the payload entirely:
    assert.ok(!('student_name' in p));
    assert.ok(!('student_email' in p));
    assert.ok(!('account_holder' in p));
    assert.ok(!('relationship' in p));
    assert.ok(!('no_key_channel' in p));
});

test('buildPayoutRegistrationPayload marks has_key=false for a blank key', () => {
    const p = u.buildPayoutRegistrationPayload({ pkHash: 'pk-abcdef123456', pixKey: '' });
    assert.strictEqual(p.has_key, false);
});

test('PRIVACY: redacted summary NEVER contains the raw key', () => {
    const raw = '111.444.777-35';
    const s = u.buildRedactedSummary({
        pkHash: 'pk-abcdef123456', programSlug: 'crf-anapu', pixKey: raw
    });
    assert.ok(!s.includes(raw), 'raw CPF leaked into summary!');
    assert.ok(!s.includes('444'), 'middle digits leaked!');
    assert.ok(s.includes('***.***.***-35'));
    assert.ok(s.includes('[PAYOUT REGISTRATION]'));
    assert.ok(s.includes('pk-abcd'), 'identity should be shown (masked)');
});

test('PRIVACY: redacted summary of an email key never leaks the local part', () => {
    const s = u.buildRedactedSummary({ pkHash: 'pk-abcdef123456', pixKey: 'maria@example.com' });
    assert.ok(!s.includes('maria'));
    assert.ok(s.includes('m***@example.com'));
});

(async function run() {
    for (const [name, fn] of queue) {
        try { await fn(); passed++; console.log('  ok  ' + name); }
        catch (e) { failed++; console.log('FAIL  ' + name + '\n      ' + e.message); }
    }
    console.log('\n' + passed + ' passed, ' + failed + ' failed');
    process.exit(failed ? 1 : 0);
})();
