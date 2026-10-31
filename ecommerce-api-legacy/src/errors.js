class HttpError extends Error {
    constructor(status, message, options) {
        super(message, options);
        this.status = status;
    }
}

module.exports = { HttpError };
