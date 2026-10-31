const { HttpError } = require('../errors');
const { withDbError } = require('./dbErrors');

const USER_ID_PATTERN = /^[1-9]\d*$/;

function createUserController({ dataAccess, models }) {
    const { userModel, enrollmentModel } = models;

    return {
        // Usuário com matrículas não é excluído (409); verificação e exclusão na mesma transação.
        async deleteUser(rawId) {
            if (!USER_ID_PATTERN.test(rawId)) throw new HttpError(400, 'ID inválido');
            const userId = Number(rawId);
            await withDbError('Erro DB', () => dataAccess.transaction(async (db) => {
                const user = await userModel.findById(db, userId);
                if (!user) throw new HttpError(404, 'Usuário não encontrado');
                if (await enrollmentModel.countByUser(db, userId) > 0) {
                    throw new HttpError(409, 'Usuário possui matrículas');
                }
                await userModel.deleteById(db, userId);
            }));
            return 'Usuário deletado';
        },
    };
}

module.exports = { createUserController };
