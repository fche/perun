"""Basic tests for checking degradation between versions and profiles."""

import os
import git
import pytest

import perun.utils.log as log
import perun.logic.config as config
import perun.logic.store as store
import perun.check.factory as check
import perun.check.average_amount_threshold as aat
import perun.check.best_model_order_equality as bmoe
import perun.check.fast_check as fast
import perun.check.exclusive_time_outliers as eto

__author__ = 'Tomas Fiedor'


def test_degradation_precollect(monkeypatch, pcs_full, capsys):
    """Set of basic tests for testing degradation in concrete minor version point

    Expects correct behaviour
    """
    matrix = config.Config('local', '', {
        'vcs': {'type': 'git', 'url': '../'},
        'cmds': ['ls'],
        'args': ['-al'],
        'workloads': ['.', '..'],
        'collectors': [
            {'name': 'time', 'params': {
                'warmup': 1,
                'repeat': 1
            }}
        ],
        'postprocessors': [],
        'execute': {
            'pre_run': [
                'ls | grep "."',
            ]
        },
        'degradation': {
            'collect_before_check': 'true',
            'apply': 'first',
            'strategies': [{
                'method': 'aat'
            }]
        }
    })
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)
    git_repo = git.Repo(pcs_full.get_vcs_path())
    head = str(git_repo.head.commit)

    check.degradation_in_minor(head)
    out, err = capsys.readouterr()
    assert err == ""

    def raise_sysexit(*_):
        """Raises System Exit ;)"""
        raise SystemExit()
    check.pre_collect_profiles.minor_version_cache.clear()
    monkeypatch.setattr("perun.logic.runner.run_matrix_job", raise_sysexit)
    check.degradation_in_minor(head)
    out, err = capsys.readouterr()
    assert err == ""


def test_degradation_in_minor(pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation in concrete minor version point

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.get_vcs_path())
    head = str(git_repo.head.commit)

    check.degradation_in_minor(head)
    out, err = capsys.readouterr()
    assert "Optimization" in out
    assert err == ""


def test_degradation_in_history(pcs_with_degradations):
    """Set of basic tests for testing degradation in while history

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.get_vcs_path())
    head = str(git_repo.head.commit)

    result = check.degradation_in_history(head)
    assert check.PerformanceChange.Degradation in [r[0].result for r in result]


def test_degradation_between_profiles(pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    pool_path = os.path.join(os.path.split(__file__)[0], 'profiles', 'degradation_profiles')
    profiles = [
        store.load_profile_from_file(os.path.join(pool_path, 'linear_base.perf'), True),
        store.load_profile_from_file(os.path.join(pool_path, 'linear_base_degradated.perf'), True),
        store.load_profile_from_file(os.path.join(pool_path, 'quad_base.perf'), True),
        store.load_profile_from_file(os.path.join(pool_path, 'zero.perf'), True)
    ]
    tracer_profiles = [
        store.load_profile_from_file(os.path.join(pool_path, 'tracer_baseline.perf'), True),
        store.load_profile_from_file(os.path.join(pool_path, 'tracer_target.perf'), True)
    ]

    # Test degradation detection using ETO
    result = list(eto.exclusive_time_outliers(tracer_profiles[0], tracer_profiles[1]))
    expected_changes = {check.PerformanceChange.TotalDegradation, check.PerformanceChange.NoChange}
    assert expected_changes & set(r.result for r in result)

    # Test degradation detection using ETO on the same profile - no Degradation should be found.
    result = list(eto.exclusive_time_outliers(tracer_profiles[0], tracer_profiles[0]))
    # We allow TotalDegradation and TotalOptimization since one them is always reported
    allowed = {
        check.PerformanceChange.NoChange, check.PerformanceChange.TotalDegradation,
        check.PerformanceChange.TotalOptimization
    }
    # No other result should be present here
    assert not set(r.result for r in result) - allowed

    # Cannot detect degradation using BMOE strategy betwen these pairs of profiles,
    # since the best models are same with good confidence
    result = list(bmoe.best_model_order_equality(profiles[0], profiles[1]))
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # Can detect degradation using BMOE strategy betwen these pairs of profiles
    result = list(bmoe.best_model_order_equality(profiles[1], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]

    result = list(bmoe.best_model_order_equality(profiles[0], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]

    result = list(aat.average_amount_threshold(profiles[1], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]

    # Can detect optimizations both using BMOE and AAT and Fast
    result = list(aat.average_amount_threshold(profiles[2], profiles[1]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]

    result = list(fast.fast_check(profiles[2], profiles[1]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]

    result = list(bmoe.best_model_order_equality(profiles[2], profiles[1]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]

    # Try that we printed confidence
    deg_list = [(res, "", "") for res in result]
    log.print_list_of_degradations(deg_list)
    out, _ = capsys.readouterr()
    assert 'with confidence' in out

    # Try that nothing is wrong when the average is 0.0
    result = list(aat.average_amount_threshold(profiles[3], profiles[3]))
    # Assert that DegradationInfo was yield
    assert result
    # Assert there was no change
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # Test incompatible profiles
    pool_path = os.path.join(os.path.split(__file__)[0], 'profiles', 'full_profiles')
    lhs = store.load_profile_from_file(os.path.join(pool_path, 'prof-1-time-2017-03-19-19-17-36.perf'), True)
    rhs = store.load_profile_from_file(os.path.join(pool_path, 'prof-3-memory-2017-05-15-15-43-42.perf'), True)
    with pytest.raises(SystemExit):
        check.degradation_between_files(lhs, rhs, "HEAD", 'all')
    _, err = capsys.readouterr()
    assert 'incompatible configurations' in err


def test_strategies():
    """Set of basic tests for handling the strategies

    Expects correct behaviour
    """
    pool_path = os.path.join(os.path.split(__file__)[0], 'profiles', 'degradation_profiles')
    profile = store.load_profile_from_file(os.path.join(pool_path, 'linear_base.perf'), True)
    rule = {
        'method': 'average_amount_threshold',
        'collector': 'complexity',
        'postprocessor': 'regression_analysis'
    }
    assert check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'postprocessor': 'regression_analysis',
        'collector': 'complexity'
    }
    assert check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'postprocessor': 'regression_analysis',
        'collector': 'memory'
    }
    assert not check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'collector': 'complexity',
        'postprocessor': 'normalizer'
    }
    assert not check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'collector': 'complexity',
        'cmd': 'bogus'
    }
    assert not check.is_rule_applicable_for(rule, profile)
