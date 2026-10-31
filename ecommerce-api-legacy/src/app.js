const express = require('express');
const { loadConfig, ConfigError } = require('./config');
const { openDatabase, createDataAccess, initSchema } = require('./database');
const { hashPassword } = require('./passwordHash');
const userModel = require('./models/userModel');
const courseModel = require('./models/courseModel');
const enrollmentModel = require('./models/enrollmentModel');
const paymentModel = require('./models/paymentModel');
const auditLogModel = require('./models/auditLogModel');
const financialReport = require('./models/financialReport');
const { createCheckoutController } = require('./controllers/checkoutController');
const { createReportController } = require('./controllers/reportController');
const { createUserController } = require('./controllers/userController');
const { checkoutRoutes } = require('./routes/checkoutRoutes');
const { adminRoutes } = require('./routes/adminRoutes');
const { userRoutes } = require('./routes/userRoutes');
const { errorHandler } = require('./middlewares/errorHandler');

const defaultModels = { userModel, courseModel, enrollmentModel, paymentModel, auditLogModel, financialReport };

// Monta o app sobre um acesso a dados já inicializado; models podem ser substituídos em testes.
function createApp(dataAccess, { adminToken = null, models = {} } = {}) {
    const deps = { dataAccess, models: { ...defaultModels, ...models } };
    const app = express();
    app.use(express.json());
    app.use(checkoutRoutes(createCheckoutController(deps)));
    app.use(adminRoutes(createReportController(deps), adminToken));
    app.use(userRoutes(createUserController(deps), adminToken));
    app.use(errorHandler);
    return app;
}

// Configuração é validada antes de abrir o banco; schema e seed terminam antes de abrir a porta.
async function start() {
    const config = loadConfig();
    const seedPasswordHash = await hashPassword(config.seedUserPassword);
    const db = await openDatabase(config.databasePath);
    const dataAccess = createDataAccess(db);
    await initSchema(dataAccess, { seedPasswordHash });
    const app = createApp(dataAccess, { adminToken: config.adminToken });
    await new Promise((resolve, reject) => {
        const server = app.listen(config.port, resolve);
        server.once('error', reject);
    });
    console.log(`Frankenstein LMS rodando na porta ${config.port}...`);
}

if (require.main === module) {
    start().catch((err) => {
        if (err instanceof ConfigError) {
            console.error(err.message);
        } else {
            console.error(`Falha na inicialização: ${err.message}`);
        }
        process.exit(1);
    });
}

module.exports = { createApp, start };
