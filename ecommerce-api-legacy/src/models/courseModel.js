async function findActiveById(db, id) {
    return db.get('SELECT id, title, price FROM courses WHERE id = ? AND active = 1', [id]);
}

module.exports = { findActiveById };
