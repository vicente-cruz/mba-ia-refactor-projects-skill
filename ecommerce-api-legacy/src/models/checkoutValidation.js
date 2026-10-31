const { HttpError } = require('../errors');

const isNonEmptyString = (value) => typeof value === 'string' && value.length > 0;

function isValidPassword(value) {
    return isNonEmptyString(value);
}

// Valida tipos do corpo do checkout. A exigência de senha depende de o usuário ser novo
// e por isso é verificada pelo controller, após consultar o banco.
function validateCheckout(body) {
    const { usr, eml, pwd, c_id: courseId, card } = body || {};
    const validCourseId = (typeof courseId === 'number' || typeof courseId === 'string') && Boolean(courseId);
    if (!isNonEmptyString(usr) || !isNonEmptyString(eml) || !isNonEmptyString(card) || !validCourseId) {
        throw new HttpError(400, 'Bad Request');
    }
    return { userName: usr, email: eml, password: pwd, courseId, card };
}

module.exports = { validateCheckout, isValidPassword };
