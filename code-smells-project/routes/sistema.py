from flask import Blueprint, current_app, jsonify, request

from auth import require_admin_token
from controllers import sistema_controller
from database import get_db

sistema_bp = Blueprint("sistema", __name__)


@sistema_bp.route("/")
def index():
    return jsonify(sistema_controller.indice())


@sistema_bp.route("/health", methods=["GET"])
def health_check():
    dados, saudavel = sistema_controller.health_check(get_db, current_app.config["DEBUG"])
    return jsonify(dados), 200 if saudavel else 500


@sistema_bp.route("/admin/reset-db", methods=["POST"])
@require_admin_token
def reset_database():
    sistema_controller.resetar_banco(get_db())
    return jsonify({"mensagem": "Banco de dados resetado", "sucesso": True}), 200


@sistema_bp.route("/admin/query", methods=["POST"])
@require_admin_token
def executar_query():
    resultado = sistema_controller.executar_consulta(get_db(), request.get_json(silent=True))
    return jsonify({"dados": resultado, "sucesso": True}), 200
