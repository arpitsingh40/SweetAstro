"""Answer-quality eval tests: rubric behaviour + golden payload cases."""

from SweetAstro.src.evaluation.chat_quality import (
    GOLDEN_CASES, ChatQualityContext, GoldenCase, evaluate_payload,
    render_golden_report, run_golden_cases, score_chat_answer,
)

PAYLOAD = (
    "Ascendant: Libra 12.34°\n"
    "Moon: Leo 5.67°, Nakshatra Purva Phalguni pada 2\n"
    "Current Vimshottari dasha: Sun MD / Moon AD / Venus PD\n"
)


def _good_answer(*, include_referral=True, disclose_recall=True, timing_text="The engine withholds event timing because the natal promise is weak."):
    referral = "- Please consult a qualified professional for health matters.\n" if include_referral else ""
    recall = "- The birth time used here was recalled from your saved profile; correct it if needed.\n" if disclose_recall else ""
    return (
        "🔮 Bottom Line\nThe chart suggests steady growth. (Libra, Leo, Sun MD / Moon AD)\n"
        "🧩 Key Chart Factors\n1. Ascendant Libra with Moon in Leo.\n2. Sun MD operating.\n3. Moon AD supporting.\n"
        f"⏳ Timing\n{timing_text}\n"
        "📈 Opportunity\nSupportive period for effort.\n"
        "⚠️ Risk\nWatch overextension.\n"
        "🪐 Recommended Alignment\nSteady discipline.\n"
        "🕉️ Traditional Remedies\nPrimary practice with safety note.\n"
        "🎯 What You Should Do\n1. Keep a routine.\n"
        f"{referral}{recall}"
        "Confidence\nMedium\nReason:\nBirth time reliable; factors partly agree.\n"
        "Remedy Suitability\nModerate\nReason:\nChart supports gentle practices.\n"
    )


def test_good_answer_scores_clean():
    context = ChatQualityContext(topic="health", referrals_expected=True, used_saved_time=True)
    report = score_chat_answer(_good_answer(), payload=PAYLOAD, context=context)
    assert report.score == 100, [(i.dimension, i.detail) for i in report.issues]
    assert report.high_issues == []


def test_absolute_language_is_flagged():
    answer = _good_answer().replace("The chart suggests steady growth.",
                                    "You will definitely get married in March 2028.")
    report = score_chat_answer(answer, payload=PAYLOAD,
                               context=ChatQualityContext())
    assert any(i.dimension == "calibration" for i in report.issues)


def test_promise_gate_violation_is_flagged():
    answer = _good_answer(timing_text="A clear window is March 2028.")
    context = ChatQualityContext(timing_withheld=True)
    report = score_chat_answer(answer, payload=PAYLOAD, context=context)
    assert any(i.dimension == "promise_gate" and i.severity == "high" for i in report.issues)


def test_missing_referrals_and_recall_disclosure_are_flagged():
    answer = _good_answer(include_referral=False, disclose_recall=False)
    context = ChatQualityContext(referrals_expected=True, used_saved_time=True)
    report = score_chat_answer(answer, payload=PAYLOAD, context=context)
    dims = {i.dimension for i in report.issues}
    assert "safety_hygiene" in dims
    assert "disclosure" in dims


def test_missing_sections_and_weak_grounding_are_flagged():
    report = score_chat_answer("A short generic reply.", payload=PAYLOAD,
                               context=ChatQualityContext())
    dims = {i.dimension for i in report.issues}
    assert "completeness" in dims
    assert "grounding" in dims
    assert report.score < 70


def test_golden_cases_all_pass():
    results = run_golden_cases()
    failures = {r.key: r.failures for r in results if not r.passed}
    assert not failures, failures


def test_evaluate_payload_detects_leaks_and_gaps():
    case = GoldenCase(key="x", question="?", extraction={},
                      must_contain=["REQUIRED"],
                      must_not_contain=["FORBIDDEN"])
    ok = evaluate_payload(case, "REQUIRED and nothing else")
    assert ok.passed
    bad = evaluate_payload(case, "FORBIDDEN only")
    assert not bad.passed
    assert any(f.startswith("missing:") for f in bad.failures)
    assert any(f.startswith("leaked:") for f in bad.failures)


def test_golden_report_renders():
    text = render_golden_report(run_golden_cases())
    assert "# Chat payload golden cases" in text
    assert f"{len(GOLDEN_CASES)}/" in text
