from flask import Blueprint, jsonify, request

from auth import require_admin_token
from controllers import usuario_controller

usuarios_bp = Blueprint("usuarios", __name__)


@usuarios_bp.route("/usuarios", methods=["GET"])
@require_admin_token
def listar_usuarios():
    return jsonify({"dados": usuario_controller.listar_usuarios(), "sucesso": True}), 200


@usuarios_bp.route("/usuarios/<int:usuario_id>", methods=["GET"])
@require_admin_token
def buscar_usuario(usuario_id):
    return jsonify({"dados": usuario_controller.buscar_usuario(usuario_id), "sucesso": True}), 200


@usuarios_bp.route("/usuarios", methods=["POST"])
def criar_usuario():
    usuario_id = usuario_controller.criar_usuario(request.get_json(silent=True))
    return jsonify({"dados": {"id": usuario_id}, "sucesso": True}), 201


@usuarios_bp.route("/login", methods=["POST"])
def login():
    usuario = usuario_controller.login(request.get_json(silent=True))
    return jsonify({"dados": usuario, "sucesso": True, "mensagem": "Login OK"}), 200
