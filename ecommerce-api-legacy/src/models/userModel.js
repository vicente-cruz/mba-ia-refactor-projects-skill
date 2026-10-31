async function findIdByEmail(db, email) {
    return db.get('SELECT id FROM users WHERE email = ?', [email]);
}

async function findById(db, id) {
    return db.get('SELECT id FROM users WHERE id = ?', [id]);
}

async function create(db, { name, email, passwordHash }) {
    const { lastID } = await db.run('INSERT INTO users (name, email, pass) VALUES (?, ?, ?)', [name, email, passwordHash]);
    return lastID;
}

async function deleteById(db, id) {
    await db.run('DELETE FROM users WHERE id = ?', [id]);
}

module.exports = { findIdByEmail, findById, create, deleteById };
