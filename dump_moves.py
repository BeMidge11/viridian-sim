from data.moves import load_move_pool

def dump():
    move_pool = load_move_pool()
    # Sort alphabetically for readability
    sorted_moves = sorted(move_pool, key=lambda m: m.name)
    
    print(f"Total Moves in Randomization Pool: {len(sorted_moves)}")
    print("-" * 40)
    for m in sorted_moves:
        cat = "Physical" if m.name in {"scratch", "tackle"} or m.power > 0 else "Status"
        # Just printing names to avoid overwhelming the user, they can ask for more details if needed
        print(f"{m.name:<20} | {m.type:<10} | Power: {m.power:>3} | Acc: {m.accuracy:>3}")

if __name__ == "__main__":
    dump()
