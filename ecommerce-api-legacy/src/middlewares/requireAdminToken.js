const crypto = require('node:crypto');
const { HttpError } = require('../errors');

const digest = (value) => crypto.createHash('sha256').update(value).digest();

// Compara digests SHA-256 em tempo constante para não revelar o tamanho do token.
function requireAdminToken(expectedToken) {
    return (req, res, next) => {
        if (!expectedToken) return next(new HttpError(403, 'Operação administrativa desabilitada'));
        const provided = req.get('X-Admin-Token');
        if (provided === undefined || !crypto.timingSafeEqual(digest(provided), digest(expectedToken))) {
            return next(new HttpError(401, 'Não autorizado'));
        }
        return next();
    };
}

module.exports = { requireAdminToken };
