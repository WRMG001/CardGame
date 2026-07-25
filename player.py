from modules.database import connect


def get_player(player_id):

    conn = connect()

    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM players WHERE player_id=?",
        (player_id,)
    )

    data = cur.fetchone()

    conn.close()

    return data