from flask import Blueprint, jsonify, request

from auth import require_admin_token
from controllers import sistema_controller

sistema_bp = Blueprint("sistema", __name__)


@sistema_bp.route("/")
def index():
    return jsonify(sistema_controller.indice())


@sistema_bp.route("/health", methods=["GET"])
def health_check():
    dados, saudavel = sistema_controller.health_check()
    return jsonify(dados), 200 if saudavel else 500


@sistema_bp.route("/admin/reset-db", methods=["POST"])
@require_admin_token
def reset_database():
    sistema_controller.resetar_banco()
    return jsonify({"mensagem": "Banco de dados resetado", "sucesso": True}), 200


@sistema_bp.route("/admin/query", methods=["POST"])
@require_admin_token
def executar_query():
    resultado = sistema_controller.executar_consulta(request.get_json(silent=True))
    return jsonify({"dados": resultado, "sucesso": True}), 200
