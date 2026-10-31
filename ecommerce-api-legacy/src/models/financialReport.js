const { PAYMENT_STATUS } = require('./paymentModel');

const UNKNOWN_STUDENT = 'Unknown';

// Uma única consulta (antes: 1 + C + 2E). Cada matrícula usa no máximo um pagamento: o de menor id.
const REPORT_SQL = `
    SELECT c.id AS course_id, c.title AS course_title,
           e.id AS enrollment_id,
           u.id AS user_id, u.name AS user_name,
           p.id AS payment_id, p.amount AS payment_amount, p.status AS payment_status
    FROM courses c
    LEFT JOIN enrollments e ON e.course_id = c.id
    LEFT JOIN users u ON u.id = e.user_id
    LEFT JOIN payments p ON p.id = (SELECT MIN(id) FROM payments WHERE enrollment_id = e.id)
    ORDER BY c.id, e.id`;

// revenue soma apenas pagamentos PAID; students[].paid mostra o valor de qualquer pagamento existente.
async function build(db) {
    const rows = await db.all(REPORT_SQL);
    const courses = new Map();
    for (const row of rows) {
        if (!courses.has(row.course_id)) {
            courses.set(row.course_id, { course: row.course_title, revenue: 0, students: [] });
        }
        if (row.enrollment_id === null) continue;
        const courseData = courses.get(row.course_id);
        const hasPayment = row.payment_id !== null;
        if (hasPayment && row.payment_status === PAYMENT_STATUS.PAID) {
            courseData.revenue += row.payment_amount;
        }
        courseData.students.push({
            student: row.user_id !== null ? row.user_name : UNKNOWN_STUDENT,
            paid: hasPayment ? row.payment_amount : 0,
        });
    }
    return [...courses.values()];
}

module.exports = { build };
