"""Regression analysis postprocessor module."""

import click

import perun.logic.runner as runner
import perun.postprocess.regression_analysis.data_provider as data_provider
import perun.postprocess.regression_analysis.tools as tools
from perun.utils.helpers import PostprocessStatus, pass_profile
from perun.postprocess.regression_analysis.methods import get_supported_methods, compute
from perun.postprocess.regression_analysis.regression_models import get_supported_models

__author__ = 'Jiri Pavela'

_DEFAULT_STEPS = 5


def postprocess(profile, **configuration):
    # Validate the input configuration
    tools.validate_dictionary_keys(configuration, ['method', 'regression_models', 'steps'], [])
    analysis = compute(data_provider.data_provider_mapper(profile), configuration['method'],
                       configuration['regression_models'], steps=configuration['steps'])
    profile['global']['regression_analysis'] = analysis
    return PostprocessStatus.OK, "", {'profile': profile}


@click.command()
@click.option('--method', '-m', type=click.Choice(get_supported_methods()), required=True,
              help='The regression method that will be used for computation.')
# fixme: default value not working for opt? (default='all' - help shows 'all' as default but error message shows 'a')
@click.option('--regression_models', '-r', type=click.Choice(get_supported_models()), required=False, multiple=True,
              help='List of regression models used by the regression method to fit the data.')
@click.option('--steps', '-s', type=int, required=False, default=_DEFAULT_STEPS,
              help='The number of steps / data parts used by the iterative, interval and initial guess methods')
@pass_profile
def regression_analysis(profile, **kwargs):
    """Computation of the best fitting regression model from the profile data."""
    runner.run_postprocessor_on_profile(profile, 'regression_analysis', kwargs)
