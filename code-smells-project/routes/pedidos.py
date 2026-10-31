from flask import Blueprint, jsonify, request

from controllers import pedido_controller

pedidos_bp = Blueprint("pedidos", __name__)


@pedidos_bp.route("/pedidos", methods=["POST"])
def criar_pedido():
    resultado = pedido_controller.criar_pedido(request.get_json(silent=True))
    return jsonify({"dados": resultado, "sucesso": True, "mensagem": "Pedido criado com sucesso"}), 201


@pedidos_bp.route("/pedidos", methods=["GET"])
def listar_todos_pedidos():
    return jsonify({"dados": pedido_controller.listar_todos_pedidos(), "sucesso": True}), 200


@pedidos_bp.route("/pedidos/usuario/<int:usuario_id>", methods=["GET"])
def listar_pedidos_usuario(usuario_id):
    return jsonify({"dados": pedido_controller.listar_pedidos_usuario(usuario_id), "sucesso": True}), 200


@pedidos_bp.route("/pedidos/<int:pedido_id>/status", methods=["PUT"])
def atualizar_status_pedido(pedido_id):
    pedido_controller.atualizar_status_pedido(pedido_id, request.get_json(silent=True))
    return jsonify({"sucesso": True, "mensagem": "Status atualizado"}), 200
