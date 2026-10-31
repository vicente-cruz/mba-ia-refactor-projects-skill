from flask import Blueprint, jsonify, request

from controllers import produto_controller

produtos_bp = Blueprint("produtos", __name__)


@produtos_bp.route("/produtos", methods=["GET"])
def listar_produtos():
    return jsonify({"dados": produto_controller.listar_produtos(), "sucesso": True}), 200


@produtos_bp.route("/produtos/busca", methods=["GET"])
def buscar_produtos():
    resultados = produto_controller.buscar_produtos(
        request.args.get("q", ""),
        request.args.get("categoria", None),
        request.args.get("preco_min", None),
        request.args.get("preco_max", None),
    )
    return jsonify({"dados": resultados, "total": len(resultados), "sucesso": True}), 200


@produtos_bp.route("/produtos/<int:produto_id>", methods=["GET"])
def buscar_produto(produto_id):
    return jsonify({"dados": produto_controller.buscar_produto(produto_id), "sucesso": True}), 200


@produtos_bp.route("/produtos", methods=["POST"])
def criar_produto():
    produto_id = produto_controller.criar_produto(request.get_json(silent=True))
    return jsonify({"dados": {"id": produto_id}, "sucesso": True, "mensagem": "Produto criado"}), 201


@produtos_bp.route("/produtos/<int:produto_id>", methods=["PUT"])
def atualizar_produto(produto_id):
    produto_controller.atualizar_produto(produto_id, request.get_json(silent=True))
    return jsonify({"sucesso": True, "mensagem": "Produto atualizado"}), 200


@produtos_bp.route("/produtos/<int:produto_id>", methods=["DELETE"])
def deletar_produto(produto_id):
    produto_controller.deletar_produto(produto_id)
    return jsonify({"sucesso": True, "mensagem": "Produto deletado"}), 200
