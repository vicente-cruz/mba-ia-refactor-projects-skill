const { HttpError } = require('../errors');

// Converte erro inesperado de banco em HttpError 500 com mensagem controlada; erros HTTP passam intactos.
async function withDbError(message, operation) {
    try {
        return await operation();
    } catch (err) {
        if (err instanceof HttpError) throw err;
        throw new HttpError(500, message, { cause: err });
    }
}

module.exports = { withDbError };
