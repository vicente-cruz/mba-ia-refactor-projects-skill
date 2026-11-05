from flask import Blueprint, jsonify

from auth import require_admin_token
from controllers import relatorio_controller
from database import get_db

relatorios_bp = Blueprint("relatorios", __name__)


@relatorios_bp.route("/relatorios/vendas", methods=["GET"])
@require_admin_token
def relatorio_vendas():
    return jsonify({"dados": relatorio_controller.relatorio_vendas(get_db()), "sucesso": True}), 200
