"""Дополнительные проверки fail-closed; исходный каталог tests/ не изменён."""
import copy
import unittest

from evaluation.solution import quality_gate, score


def fixture():
    rows = [dict(id=f'q{i}', expected='B', choices=['A', 'B'], slices=['all', f's{i % 3}'])
            for i in range(50)]
    out = [dict(id=r['id'], raw='{"answer":"B"}', error=None) for r in rows]
    result = score(rows, out)
    behavior = [dict(r, id=f'behavior-{i}') for i, r in enumerate(rows[:3])]
    result.update(status='complete', model=dict(kind='fixture'), protocol_sha256='p',
                  golden_sha256='g', baseline_spec_sha256='b',
                  behavioral=score(behavior, [dict(id=r['id'], raw='{"answer":"B"}', error=None) for r in behavior]))
    return rows, out, result


class ExtraContract(unittest.TestCase):
    def test_duplicate_json_keys_and_nonstandard_constants_are_invalid(self):
        rows, _, _ = fixture()
        for raw in ['{"answer":"A","answer":"B"}', '{"answer":"B","x":NaN}',
                    '{"answer":Infinity}', '[{"answer":"B"}]', 'true',
                    '{"answer":"B"} trailing']:
            with self.subTest(raw=raw):
                result = score(rows[:1], [dict(id='q0', raw=raw, error=None)])
                self.assertEqual(result['overall']['valid'], 0)

    def test_generation_error_invalidates_even_correct_json(self):
        rows, out, _ = fixture()
        out[0]['error'] = 'timeout'
        result = score(rows[:1], out[:1])
        self.assertEqual(result['overall'], dict(n=1, correct=0, valid=0, errors=1, accuracy=0, format_rate=0))
        self.assertEqual(result['per_item'][0]['raw'], '{"answer":"B"}')

    def test_overlapping_slices_do_not_inflate_overall_n(self):
        rows, out, _ = fixture()
        result = score(rows, out)
        self.assertEqual(result['overall']['n'], 50)
        self.assertEqual(result['slices']['all']['n'], 50)
        self.assertEqual(sum(s['n'] for s in result['slices'].values()), 100)

    def test_duplicate_questions_and_unknown_outputs_are_contract_errors(self):
        rows, out, _ = fixture()
        with self.assertRaises(ValueError):
            score([rows[0], rows[0]], out[:2])
        with self.assertRaises(ValueError):
            score(rows[:1], [dict(out[0], id='unknown')])

    def test_bad_baseline_rejected_too(self):
        _, _, good = fixture()
        bad = copy.deepcopy(good)
        bad['overall']['format_rate'] = float('inf')
        with self.assertRaises(ValueError):
            quality_gate(bad, good, ['s0'])

    def test_changed_slice_membership_rejected_even_with_same_sizes(self):
        rows, out, baseline = fixture()
        rows[0]['slices'], rows[1]['slices'] = rows[1]['slices'], rows[0]['slices']
        candidate = dict(baseline, **score(rows, out))
        with self.assertRaises(ValueError):
            quality_gate(baseline, candidate, ['s0'])

    def test_forged_raw_or_counts_rejected(self):
        _, _, baseline = fixture()
        for mutate in [lambda c: c['overall'].update(n=True),
                       lambda c: c['per_item'][0].update(raw='INVALID'),
                       lambda c: c['slices']['s0'].update(valid=0),
                       lambda c: c['behavioral']['per_item'][0].update(error='OOM')]:
            candidate = copy.deepcopy(baseline)
            mutate(candidate)
            with self.assertRaises(ValueError):
                quality_gate(baseline, candidate, ['s0'])

    def test_behavioral_population_must_match(self):
        _, _, baseline = fixture()
        candidate = copy.deepcopy(baseline)
        candidate['behavioral']['per_item'][0]['id'] = 'different'
        with self.assertRaises(ValueError):
            quality_gate(baseline, candidate, ['s0'])

    def test_empty_critical_slices_cannot_disable_protection(self):
        _, _, report = fixture()
        with self.assertRaises(ValueError):
            quality_gate(report, report, [])


if __name__ == '__main__':
    unittest.main()
