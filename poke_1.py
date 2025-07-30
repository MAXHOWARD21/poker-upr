# writing your own code

import json
import os
from typing import List, Dict

PLAYER_DATA_FILE = 'players.json'


class Player:
    def __init__(self, name: str, rating: float = 1500.0):
        self.name = name
        self.rating = rating

    def to_dict(self):
        return {'name': self.name, 'rating': self.rating}

    @staticmethod
    def from_dict(data):
        return Player(data['name'], data['rating'])


class PlayerDatabase:
    def __init__(self, filename=PLAYER_DATA_FILE):
        self.filename = filename
        self.players: Dict[str, Player] = self.load_players()

    def load_players(self) -> Dict[str, Player]:
        if not os.path.exists(self.filename):
            return {}
        with open(self.filename, 'r') as f:
            data = json.load(f)
            return {p['name']: Player.from_dict(p) for p in data}

    def save_players(self):
        with open(self.filename, 'w') as f:
            json.dump([p.to_dict()
                      for p in self.players.values()], f, indent=2)

    def get_player(self, name: str) -> Player:
        if name not in self.players:
            self.players[name] = Player(name)
        return self.players[name]

    def update_player(self, player: Player):
        self.players[player.name] = player
        self.save_players()


class Session:
    def __init__(self, players: List[str], buyins: List[float], cashouts: List[float], blind_size: float):
        self.players = players
        self.buyins = buyins
        self.cashouts = cashouts
        self.blind_size = blind_size
        self.results = [c - b for b, c in zip(buyins, cashouts)]

    def get_results(self):
        return dict(zip(self.players, self.results))


def elo_update(player_a: Player, player_b: Player, result: float, k: float):
    # result: 1.0 if a beats b, 0.0 if b beats a, 0.5 for tie
    expected_a = 1 / (1 + 10 ** ((player_b.rating - player_a.rating) / 400))
    change = k * (result - expected_a)
    player_a.rating += change
    player_b.rating -= change
    return change


def process_session(session: Session, db: PlayerDatabase, k_base: float = 32.0):
    # For each pair of players, update ELO based on profit
    n = len(session.players)
    for i in range(n):
        for j in range(i + 1, n):
            name_a, name_b = session.players[i], session.players[j]
            profit_a, profit_b = session.results[i], session.results[j]
            player_a = db.get_player(name_a)
            player_b = db.get_player(name_b)
            if profit_a > profit_b:
                result = 1.0
            elif profit_a < profit_b:
                result = 0.0
            else:
                result = 0.5
            # Weight by blind size (stakes)
            k = k_base * session.blind_size
            elo_update(player_a, player_b, result, k)
            db.update_player(player_a)
            db.update_player(player_b)


def print_rankings(db: PlayerDatabase):
    players = sorted(db.players.values(), key=lambda p: p.rating, reverse=True)
    print("\nCurrent Player Rankings:")
    for i, player in enumerate(players, 1):
        print(f"{i}. {player.name}: {player.rating:.1f}")
    print()


def input_float_list(prompt, n):
    while True:
        try:
            values = input(prompt).strip().split(',')
            if len(values) != n:
                print(f"Please enter {n} values, separated by commas.")
                continue
            return [float(v.strip()) for v in values]
        except ValueError:
            print("Invalid input. Please enter numbers separated by commas.")


def cli_loop():
    db = PlayerDatabase()
    print("Welcome to the Poker ELO Rating System!")
    while True:
        print("\n--- New Session ---")
        names = input(
            "Enter player names (comma-separated): ").strip().split(',')
        names = [n.strip() for n in names if n.strip()]
        if not names:
            print("No players entered. Try again.")
            continue
        buyins = input_float_list(
            f"Enter buy-ins for {', '.join(names)} (comma-separated): ", len(names))
        cashouts = input_float_list(
            f"Enter cash-outs for {', '.join(names)} (comma-separated): ", len(names))
        while True:
            try:
                blind_size = float(
                    input("Enter big blind size (e.g., 2 for $1/$2): ").strip())
                break
            except ValueError:
                print("Invalid blind size. Please enter a number.")
        session = Session(names, buyins, cashouts, blind_size)
        process_session(session, db)
        print_rankings(db)
        again = input("Run another session? (y/n): ").strip().lower()
        if again != 'y':
            print("Goodbye!")
            break


def main():
    cli_loop()


if __name__ == '__main__':
    main()
