const { withDbError } = require('./dbErrors');

function createReportController({ dataAccess, models }) {
    return {
        financialReport() {
            return withDbError('Erro DB', () => dataAccess.read((db) => models.financialReport.build(db)));
        },
    };
}

module.exports = { createReportController };
