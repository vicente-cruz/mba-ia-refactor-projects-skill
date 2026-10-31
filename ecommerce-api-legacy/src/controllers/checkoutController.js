const { HttpError } = require('../errors');
const { hashPassword: defaultHashPassword } = require('../passwordHash');
const { validateCheckout, isValidPassword } = require('../models/checkoutValidation');
const { withDbError } = require('./dbErrors');

function createCheckoutController({ dataAccess, models, hashPassword = defaultHashPassword }) {
    const { userModel, courseModel, enrollmentModel, paymentModel, auditLogModel } = models;

    return {
        async checkout(body) {
            const { userName, email, password, courseId, card } = validateCheckout(body);
            const paymentStatus = paymentModel.authorize(card);
            // O hash é calculado fora da fila do banco; só é usado se o usuário for novo.
            const passwordHash = isValidPassword(password) ? await hashPassword(password) : null;

            // Leituras, decisões dependentes do banco e escritas numa única transação exclusiva.
            return withDbError('Erro DB', () => dataAccess.transaction(async (db) => {
                const course = await withDbError('Erro DB', () => courseModel.findActiveById(db, courseId));
                if (!course) throw new HttpError(404, 'Curso não encontrado');

                const existingUser = await withDbError('Erro DB', () => userModel.findIdByEmail(db, email));
                if (!existingUser && passwordHash === null) throw new HttpError(400, 'Bad Request');
                if (paymentStatus !== paymentModel.PAYMENT_STATUS.PAID) throw new HttpError(400, 'Pagamento recusado');

                const userId = existingUser
                    ? existingUser.id
                    : await withDbError('Erro ao criar usuário', () =>
                        userModel.create(db, { name: userName, email, passwordHash }));
                const enrollmentId = await withDbError('Erro Matrícula', () =>
                    enrollmentModel.create(db, { userId, courseId }));
                await withDbError('Erro Pagamento', () =>
                    paymentModel.create(db, { enrollmentId, amount: course.price, status: paymentStatus }));
                await withDbError('Erro Auditoria', () =>
                    auditLogModel.record(db, `Checkout curso ${courseId} por ${userId}`));

                return { msg: 'Sucesso', enrollment_id: enrollmentId };
            }));
        },
    };
}

module.exports = { createCheckoutController };
