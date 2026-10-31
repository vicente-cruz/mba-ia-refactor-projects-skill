const http = require('node:http');
const { HttpError } = require('../errors');

// Respostas de erro em texto puro. Detalhes de erros 5xx vão apenas para o log, sem dados da requisição.
function errorHandler(err, req, res, next) {
    if (res.headersSent) return next(err);
    if (err instanceof HttpError) {
        if (err.status >= 500) logError(req, err);
        return res.status(err.status).send(err.message);
    }
    // Erros 4xx do próprio Express/body-parser (ex.: JSON inválido): mensagem padrão do status, sem stack trace.
    const status = Number.isInteger(err.status) && err.status >= 400 && err.status < 500 ? err.status : 500;
    if (status >= 500) {
        logError(req, err);
        return res.status(500).send('Internal Server Error');
    }
    return res.status(status).send(http.STATUS_CODES[status]);
}

function logError(req, err) {
    const cause = err.cause ? ` | causa: ${err.cause.message}` : '';
    console.error(`[erro] ${req.method} ${req.path}: ${err.message}${cause}`);
}

module.exports = { errorHandler };
