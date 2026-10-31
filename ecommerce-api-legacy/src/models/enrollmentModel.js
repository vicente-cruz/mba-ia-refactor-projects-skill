async function create(db, { userId, courseId }) {
    const { lastID } = await db.run('INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)', [userId, courseId]);
    return lastID;
}

async function countByUser(db, userId) {
    const row = await db.get('SELECT COUNT(*) AS total FROM enrollments WHERE user_id = ?', [userId]);
    return row.total;
}

module.exports = { create, countByUser };
