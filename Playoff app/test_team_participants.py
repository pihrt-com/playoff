import unittest

import playoff


class TeamParticipantDataTests(unittest.TestCase):
    def make_app(self):
        app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
        app.team_names = [
            {"id": "10", "school": "SPŠ", "participant": "Anna Nováková", "best_time": "01:25:213"},
            {"id": "20", "desc": "Starší popis školy"},
            {"id": "30", "school": "Gymnázium", "participant": "Petr Malý", "best_time": ""},
        ]
        return app

    def test_pre_round_and_first_round_are_merged_without_duplicates(self):
        app = self.make_app()
        app.pre_round_enabled = True
        app.bracket = playoff.Bracket(["30", "10"], ["20", "10"], use_pre_round=True)
        app.bracket.pre_rounds[0][0].a.text = "20"
        app.bracket.pre_rounds[0][0].b.text = "10"

        rows = app.build_team_lookup_from_round1()

        self.assertEqual([row[0] for row in rows], ["10", "20", "30"])
        self.assertEqual(rows[0][1]["participant"], "Anna Nováková")
        self.assertEqual(rows[1][1]["school"], "Starší popis školy")

    def test_first_round_is_the_participant_source_when_pre_round_is_disabled(self):
        app = self.make_app()
        app.pre_round_enabled = False
        app.bracket = playoff.Bracket(["30", "10"], [], use_pre_round=False)

        rows = app.build_team_lookup_from_round1()

        self.assertEqual([row[0] for row in rows], ["10", "30"])

    def test_legacy_records_and_partial_excel_rows_are_normalized(self):
        legacy = playoff.normalize_team_record({"id": 7, "desc": "Původní škola"})
        partial = playoff.team_record_from_excel_row((8, None, "Jan Nový"))

        self.assertEqual(legacy, {
            "id": "7", "school": "Původní škola", "participant": "", "best_time": "",
        })
        self.assertEqual(partial, {
            "id": "8", "school": "", "participant": "Jan Nový", "best_time": "",
        })


if __name__ == "__main__":
    unittest.main()
