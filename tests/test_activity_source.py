import unittest

from tracker.activity_source import describe_task, filter_report, hours_label, normalize_report, report_csv


class DescribeTests(unittest.TestCase):
    def test_chat_task_uses_outcome(self):
        text = describe_task({
            "task": "Custom cron jobs overview",
            "category": "Testing & Verification",
            "source": "cursor_chat",
            "outcomes": ["A dry run is not possible for these ten jobs. Each execute method is the real action."],
            "user_requests": ["how can we verify this cron"],
        })
        self.assertIn("dry run is not possible", text)
        self.assertFalse(text.lower().startswith("mostly"))
        self.assertTrue(text.endswith("."))

    def test_commits_are_listed(self):
        text = describe_task({
            "source": "git_commits",
            "outcomes": ["Removed configurator from staging2", "Fixed composer.lock encoding"],
        })
        self.assertIn("Removed configurator from staging2", text)
        self.assertTrue(text.endswith("."))

    def test_zero_minute_overlap_is_dropped(self):
        report = normalize_report({
            "date": "2026-11-05",
            "projects": [{"project": "demo", "tasks": [
                {"task": "Kept", "category": "Development", "source": "cursor_chat", "minutes": 20,
                 "hours": 0.33, "duration": "20 min", "time": "9:00 AM - 9:20 AM",
                 "outcomes": ["Updated the checkout button and confirmed the order total."]},
                {"task": "Overlap", "minutes": 0, "hours": 0, "outcomes": ["ignored"]},
            ]}],
        }, "2026-11-05", "generate_timelog")
        self.assertEqual(len(report["projects"][0]["tasks"]), 1)
        self.assertEqual(report["task_count"], 1)
        self.assertIn("Updated the checkout button", report["projects"][0]["tasks"][0]["description"])

    def test_filter_and_csv(self):
        report = normalize_report({
            "date": "2026-11-05",
            "projects": [
                {"project": "one", "tasks": [{"description": "Did one.", "time": "9:00 AM", "hours": 1, "category": "Development"}]},
                {"project": "two", "tasks": [{"description": "Did two.", "time": "10:00 AM", "hours": None, "category": "Research & Analysis"}]},
            ],
        }, "2026-11-05", "generate_timelog")
        filtered = filter_report(report, "two")
        self.assertEqual([p["project"] for p in filtered["projects"]], ["two"])
        self.assertEqual(filtered["projects"][0]["tasks"][0]["hours_label"], "To be confirmed")
        csv_text = report_csv(filtered)
        self.assertIn("Did two.", csv_text)
        self.assertNotIn("Did one.", csv_text)
        self.assertTrue(csv_text.startswith("Date,Project,Activity Description,Time,Duration,Hours,Category"))

    def test_hours_label(self):
        self.assertEqual(hours_label(None, None), "To be confirmed")
        self.assertEqual(hours_label(0.83, "50 min"), "0.83 h (50 min)")


if __name__ == "__main__":
    unittest.main()
