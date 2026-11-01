from flask import Blueprint, jsonify, request

import auth
from controllers import user_controller

user_bp = Blueprint('users', __name__)


@user_bp.route('/users', methods=['GET'])
def get_users():
    return jsonify(user_controller.list_users()), 200


@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    return jsonify(user_controller.get_user(user_id)), 200


@user_bp.route('/users', methods=['POST'])
def create_user():
    actor = auth.optional_actor()
    return jsonify(user_controller.create_user(request.get_json(), actor)), 201


@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    actor = auth.require_actor()
    return jsonify(user_controller.update_user(user_id, request.get_json, actor)), 200


@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    actor = auth.require_actor()
    return jsonify(user_controller.delete_user(user_id, actor)), 200


@user_bp.route('/users/<int:user_id>/tasks', methods=['GET'])
def get_user_tasks(user_id):
    return jsonify(user_controller.get_user_tasks(user_id)), 200


@user_bp.route('/login', methods=['POST'])
def login():
    return jsonify(user_controller.login(request.get_json())), 200
