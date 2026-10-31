class ConfigError extends Error {}

const DEFAULT_PORT = 3000;

function readPort(value) {
    if (value === undefined || value === '') return DEFAULT_PORT;
    const port = Number(value);
    if (!Number.isInteger(port) || port < 0 || port > 65535) {
        throw new ConfigError('Configuração inválida: PORT deve ser um inteiro entre 0 e 65535');
    }
    return port;
}

// Lê e valida a configuração. Segredos não têm fallback no código.
function loadConfig(env = process.env) {
    const seedUserPassword = env.SEED_USER_PASSWORD;
    if (!seedUserPassword) {
        throw new ConfigError('Configuração inválida: SEED_USER_PASSWORD é obrigatória');
    }
    return {
        port: readPort(env.PORT),
        databasePath: ':memory:',
        adminToken: env.ADMIN_TOKEN || null,
        seedUserPassword,
    };
}

module.exports = { loadConfig, ConfigError };
