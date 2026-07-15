import logging
from flask import Blueprint, jsonify, request
from app.models.game import validate_guess, serialize_round, serialize_session, DEFAULT_POOL_SIZE
from app.services import game_service

logger = logging.getLogger(__name__)

game_bp = Blueprint("game", __name__, url_prefix="/game")


def _session_response(session_doc, round_doc, status=200):
    reveal = round_doc["status"] == "completed"
    return jsonify({
        "session": serialize_session(session_doc),
        "round": serialize_round(round_doc, reveal=reveal),
    }), status


@game_bp.route("/sessions", methods=["POST"])
def start_session():
    """
    Start a new No Profit session. Each session is a run of escalating
    rounds - pass a round to advance, with the allowed margin for error
    shrinking every round until you miss it and the session ends.
    ---
    tags: [Game]
    parameters:
      - name: body
        in: body
        schema:
          properties:
            player_name: {type: string}
            pool_size: {type: integer}
    responses:
      201:
        description: New session with its first round, target visible, item prices hidden
    """
    data = request.get_json(silent=True) or {}
    player_name = data.get("player_name")
    pool_size = data.get("pool_size", DEFAULT_POOL_SIZE)
    try:
        pool_size = int(pool_size)
    except (ValueError, TypeError):
        return jsonify({"error": "pool_size must be an integer"}), 422

    session_doc, round_doc = game_service.create_session(player_name, pool_size)
    return _session_response(session_doc, round_doc, status=201)


@game_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """
    Fetch a session's current state (and its current round).
    ---
    tags: [Game]
    parameters:
      - name: session_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Session + current round state
      404:
        description: Not found
    """
    session_doc = game_service.get_session(session_id)
    if not session_doc:
        return jsonify({"error": "Session not found"}), 404

    round_doc = game_service.get_round(session_doc["current_round_id"])
    return _session_response(session_doc, round_doc)


@game_bp.route("/sessions/<session_id>/guess", methods=["POST"])
def guess_session(session_id):
    """
    Submit quantities for the session's current round. If the difference
    from target is within that round's margin, the session advances to a
    tougher round; otherwise the session ends.
    ---
    tags: [Game]
    parameters:
      - name: session_id
        in: path
        type: string
        required: true
      - name: body
        in: body
        required: true
        schema:
          properties:
            player_name: {type: string}
            guesses:
              type: object
              description: Map of product_id to quantity
    responses:
      200:
        description: Revealed breakdown for the round just played, updated session, and the next round if still active
      404:
        description: Session not found
      409:
        description: Session already ended
      422:
        description: Invalid guess payload
    """
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    cleaned, err = validate_guess(data)
    if err:
        return jsonify({"error": err}), 422

    result, err = game_service.submit_session_guess(session_id, cleaned["player_name"], cleaned["guesses"])
    if err == "session_not_found" or err == "round_not_found":
        return jsonify({"error": "Session not found"}), 404
    if err == "session_already_ended":
        return jsonify({"error": "Session already ended"}), 409
    if err:
        return jsonify({"error": err}), 422

    response = {
        "session": serialize_session(result["session"]),
        "round": serialize_round(result["round"], reveal=True),
        "next_round": serialize_round(result["next_round"], reveal=False) if result["next_round"] else None,
    }
    return jsonify(response), 200


@game_bp.route("/leaderboard", methods=["GET"])
def leaderboard():
    """
    Top runs across all ended sessions, ranked by rounds survived (ties
    broken by the tightest margin reached).
    ---
    tags: [Game]
    parameters:
      - name: limit
        in: query
        type: integer
        default: 10
    responses:
      200:
        description: Leaderboard entries
    """
    limit = request.args.get("limit", 10, type=int)
    return jsonify(game_service.get_leaderboard(limit=limit)), 200
