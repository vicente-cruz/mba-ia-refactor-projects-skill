const crypto = require('node:crypto');
const { promisify } = require('node:util');

const scrypt = promisify(crypto.scrypt);

const SCHEME = 'scrypt';
const SALT_BYTES = 16;
const KEY_BYTES = 64;

async function hashPassword(password) {
    if (typeof password !== 'string') throw new TypeError('password deve ser string');
    const salt = crypto.randomBytes(SALT_BYTES);
    const derived = await scrypt(password, salt, KEY_BYTES);
    return `${SCHEME}$${salt.toString('hex')}$${derived.toString('hex')}`;
}

module.exports = { hashPassword };
