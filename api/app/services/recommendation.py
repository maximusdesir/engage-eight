"""Rules-based defensive play-call suggestions.

Given a run/pass prediction and the situation, this returns 2-3 defensive
calls in suggested order. There is no model and no score here: it is a
transparent ruleset a coach can read, so no confidence or EPA number is
attached to a call (an earlier version showed hand-set constants as if they
were measured).

Vocabulary
----------
Fronts:    Bear, Over, Under, Tite, Even
Coverages: Cover 1, Cover 3, Cover 3 Buzz, Quarters, Cover 6
Pressures: None, Sim, Creeper, Fire Zone, Cross Dog
Stunts:    None, TEX, ET, Twist
"""
from __future__ import annotations


def _call(front: str, coverage: str, pressure: str, stunt: str, rationale: str) -> dict:
    return {
        "front": front,
        "coverage": coverage,
        "pressure": pressure,
        "stunt": stunt,
        "rationale": rationale,
    }


def recommend(prediction: dict, game_state: dict) -> list[dict]:
    """Return 2-3 defensive calls for the situation, best fit first."""
    down = game_state["down"]
    distance = game_state["distance"]
    yardline_100 = game_state["yardline_100"]

    pass_prob = prediction["pass_prob"]
    run_prob = prediction["run_prob"]

    red_zone = yardline_100 <= 20
    goal_to_go = yardline_100 <= distance
    obvious_pass = down == 3 and distance >= 7
    short_yardage = distance <= 2

    # --- Obvious passing down, strong pass lean ---------------------------
    if (obvious_pass or distance >= 8) and pass_prob >= 0.6:
        return [
            _call("Even", "Cover 3 Buzz", "Fire Zone", "TEX",
                  f"{down} & {distance}, {round(pass_prob * 100)}% pass: drop into a "
                  "Cover 3 Buzz with the buzz defender robbing the intermediate, "
                  "five-man Fire Zone pressure with a TEX twist to muddy the launch "
                  "point without exposing the deep thirds."),
            _call("Tite", "Quarters", "Sim", "ET",
                  "Simulated pressure out of Quarters: show heat, drop to a 4-man "
                  "rush behind quarters to cap explosives over the top while the ET "
                  "stunt wins one-on-one inside."),
            _call("Even", "Cover 6", "Creeper", "Twist",
                  "Cover 6 (quarter-quarter-half) with a zone creeper: replace a "
                  "rusher with an off-ball defender to keep four in coverage and "
                  "split-field leverage against the boundary shot."),
        ]

    # --- Short yardage / heavy run lean -----------------------------------
    if short_yardage and run_prob >= 0.55:
        return [
            _call("Bear", "Cover 1", "Cross Dog", "None",
                  f"{down} & {distance}, {round(run_prob * 100)}% run: load a Bear front "
                  "to cover all the gaps, Cover 1 man behind it and a Cross Dog "
                  "linebacker blitz to spill the ball and win the short-yardage down."),
            _call("Over", "Cover 3", "None", "ET",
                  "Over front into Cover 3 keeps an extra hat in the box with a "
                  "safety rolled down; the ET stunt knifes the run-side gap while "
                  "staying sound against play-action over the top."),
        ]

    # --- Red zone (tight coverage, compressed field) ----------------------
    if red_zone or goal_to_go:
        if pass_prob >= 0.5:
            return [
                _call("Even", "Cover 1", "Sim", "Twist",
                      "Red zone pass look: tight Cover 1 man with a robber to wall "
                      "off crossers, simulated pressure to speed up the throw in a "
                      "compressed field where there is no deep grass to defend."),
                _call("Tite", "Quarters", "None", "TEX",
                      "Tite front, Quarters coverage: pattern-match the route "
                      "distributions and keep eyes on the quarterback for the scramble "
                      "while the TEX stunt pressures with four."),
            ]
        return [
            _call("Bear", "Cover 1", "Cross Dog", "None",
                  "Goal-line run look: Bear front to plug every gap, Cover 1 man "
                  "behind it and a Cross Dog to penetrate before the back hits "
                  "the line."),
            _call("Over", "Cover 3", "None", "ET",
                  "Over front, Cover 3 with the down safety as the extra run "
                  "fitter; ET stunt squeezes the play-side B gap."),
        ]

    # --- Balanced / early down --------------------------------------------
    if pass_prob >= 0.5:
        return [
            _call("Even", "Quarters", "None", "Twist",
                  f"{down} & {distance}, slight pass lean: stay sound in Quarters "
                  "to cap explosives, rush four with a Twist to win up front "
                  "without committing extra defenders."),
            _call("Under", "Cover 3 Buzz", "Creeper", "ET",
                  "Under front, Cover 3 Buzz with a zone creeper to disguise the "
                  "rush while keeping a defender on the intermediate hole."),
        ]
    return [
        _call("Over", "Cover 3", "None", "ET",
              f"{down} & {distance}, run lean: Over front into Cover 3 keeps "
              "the box sound with a rolled-down safety; ET stunt attacks the "
              "front-side gap."),
        _call("Tite", "Quarters", "None", "TEX",
              "Tite front spills the ball outside to unblocked overhang "
              "defenders; Quarters keeps two-high integrity against "
              "play-action."),
    ]
