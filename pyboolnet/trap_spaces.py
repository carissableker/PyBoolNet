

import logging
import sys
from typing import List, Union, Optional
import datetime
import subprocess

from pyboolnet.prime_implicants import create_constants, percolate_and_keep_constants
from pyboolnet import find_command
from pyboolnet.state_space import subspace2dict, subspace2str
from pyboolnet.prime_implicants import active_primes

CMD_GRINGO = find_command("gringo")
CMD_CLASP = find_command("clasp")

log = logging.getLogger(__name__)


def circuits(primes: dict, max_output: int = 1000, fname_asp: Optional[str] = None, representation: str = "dict"):
    """
    Computes minimal trap spaces but also distinguishes between nodes that are fixed due to being part of a circuit
    and nodes that are fix due to percolation effects.

    **arguments**:
        * *primes*: prime implicants
        * *max_output*: maximum number of returned solutions
        * *fname_asp*: file name or *None*
        * *representation*: either "str" or "dict", the representation of the trap spaces

    **returns**:
        * *circuits*: of tuples consisting of circuit nodes and percolation nodes


    **example**::

        >>> circuits(primes)
        [({'Mek': 0, 'Erk': 0},{'Raf': 1}),..]
    """
    
    return potassco_handle(primes, type_="circuits", bounds=(0, "n"), project=None, max_output=max_output, fname_asp=fname_asp, representation=representation)


def percolate_trapspace(primes: dict, trap_space: dict):
    """
    Percolates the *trap_space*.
    Does not check whether *trap_space* is really a trap space.
    Instead, it creates constants from *trap_space* and percolates the values.

    **arguments**:
        * *primes*: prime implicants
        * *trap_space*: a subspace

    **returns**:
        * *trap_space*: the percolated trap space

    **example**::

        >>> percolate_trapspace(primes, {'Mek': 0, 'Erk': 0})
        {'Raf': 1, 'Mek': 0, 'Erk': 0}
    """
    
    primes = create_constants(primes, trap_space, in_place=True)
    constants = percolate_and_keep_constants(primes)
    
    return constants


def trapspaces_that_contain_state(primes: dict, state: dict, type_: str, fname_asp: Optional[str] = None, representation: str = "dict", max_output: int = 1000):
    """
    Computes trap spaces that contain *state*.

    **arguments**:
        * *primes*: prime implicants
        * *state*: a state in dict format
        * *type_*: either "min", "max", "all" or "percolated"
        * *fname_asp*: file name or *None*
        * *representation*: either "str" or "dict", the representation of the trap spaces
        * *max_output*: maximum number of returned solutions

    **returns**:
        * *trap_spaces*: the trap spaces that contain *state*

    **example**::

        >>> trapspaces_that_contain_state(primes, {"v1":1,"v2":0,"v3":0})
    """

    return trapspaces_that_intersect_subspace(primes=primes, subspace=state, type_=type_, fname_asp=fname_asp, representation=representation, max_output=max_output)


def trapspaces_that_intersect_subspace(primes: dict, subspace: dict, type_: str, fname_asp: Optional[str] = None, representation: str = "dict", max_output: int = 1000) -> List[dict]:
    """
    Computes trap spaces that have non-empty intersection with *subspace*

    **arguments**:
        * *primes*: prime implicants
        * *subspace*: a subspace in dict format
        * *type_*: either "min", "max", "all" or "percolated"
        * *fname_asp*: file name or *None*
        * *representation*: either "str" or "dict", the representation of the trap spaces
        * *max_output*: maximum number of returned solutions

    **returns**:
        * *trap_spaces*: the trap spaces that have non-empty intersection with *subspace*

    **example**::

        >>> trapspaces_that_intersect_subspace(primes, {"v1":1,"v2":0,"v3":0})
    """
    
    assert (len(primes) >= len(subspace))
    assert (type(subspace) in [dict, str])
    
    if type(subspace) == str:
        subspace = subspace2dict(primes, subspace)
    
    relevant_primes = active_primes(primes, subspace)
    
    bounds = None
    if type_ == "max":
        bounds = (1, "n")

    tspaces = potassco_handle(primes=relevant_primes, type_=type_, bounds=bounds, project=[], max_output=max_output, fname_asp=fname_asp, representation=representation)
    
    if not tspaces:
        answer = {}
        
        if representation == "str":
            answer = subspace2str(primes, answer)
        
        return [answer]
    
    if len(subspace) == len(primes) and type_ == "min":
        if len(tspaces) > 1:
            log.error("the smallest trap space containing a state (or other space) must be unique!")
            log.error(f"found {len(tspaces)} smallest tspaces.")
            log.error(tspaces)
            sys.exit()
        
        return [tspaces.pop()]
    
    return tspaces


def trapspaces_within_subspace(primes: dict, subspace: dict, type_, fname_asp=None, representation: str = "dict", max_output: int = 1000) -> Union[List[dict], List[str]]:
    """
    Computes trap spaces contained within *subspace*

    **arguments**:
        * *primes*: prime implicants
        * *subspace*: a subspace in dict format
        * *type_*: either "min", "max", "all" or "percolated"
        * *fname_asp*: file name or *None*
        * *representation*: either "str" or "dict", the representation of the trap spaces
        * *max_output*: maximum number of returned solutions

    **returns**:
        * *trap_spaces*: the trap spaces contained within *subspace*

    **example**::

        >>> trapspaces_in_subspace(primes, {"v1":1,"v2":0,"v3":0})
    """
    
    if not subspace:
        return trap_spaces(primes, type_, max_output=max_output, fname_asp=fname_asp, representation=representation)
    
    assert (len(primes) >= len(subspace))
    assert (type(subspace) in [dict, str])
    
    if type(subspace) == str:
        subspace = subspace2dict(primes, subspace)
    
    relevant_primes = active_primes(primes, subspace)
    bounds = (len(subspace), "n")

    extra_lines = [f':- not hit("{node}",{value}).' for node, value in subspace.items()]
    extra_lines += [""]

    tspaces = potassco_handle(primes=relevant_primes, type_=type_, bounds=bounds, project=[], max_output=max_output, fname_asp=fname_asp, representation=representation, extra_lines=extra_lines)
    
    return tspaces


def smallest_trapspace(primes: dict, state: dict, representation: str = "dict"):
    """
    Returns the (unique) smallest trap space that contains *state*.
    Calls :ref:`trapspaces_that_contain_state`

    **arguments**:
        * *primes*: prime implicants
        * *state*: a state in dict format
        * *representation*: either "str" or "dict", the representation of the trap spaces

    **returns**:
        * *trap_space*: the unique minimal trap space that contains *state*

    **example**::

        >>> smallest_trapspace(primes, {"v1":1,"v2":0,"v3":0})
    """
    
    return trapspaces_that_contain_state(primes, state, type_="min", fname_asp=None, representation=representation)


def trap_spaces(primes: dict, option: str, max_output: int = 1000, fname_asp: str = None, representation: str = "dict") -> Union[List[dict], List[str]]:
    """
    Returns a list of trap spaces using the :ref:`installation_potassco` ASP solver, see :ref:`Gebser2011 <Gebser2011>`.
    For a formal introcution to trap spaces and the ASP encoding that is used for their computation see :ref:`Klarner2015(a) <klarner2015trap>`.

    The parameter *type_* must be one of *"max"*, *"min"*, *"all"* or *"percolated"* and
    specifies whether subset minimal, subset maximal, all trap spaces or all percolated trap spaces should be returned.

    .. warning::
        The number of trap spaces is easily exponential in the number of components.
        Use the safety parameter *max_output* to control the number of returned solutions.

    To create the *asp* file for inspection or manual editing, pass a file name to *fname_asp*.

    **arguments**:
        * *primes*: prime implicants
        * *type_*: either *"max"*, *"min"*, *"all"* or *"percolated"*
        * *max_output*: maximal number of trap spaces to return
        * *fname_asp*: name of *asp* file to create, or *None*
        * *representation*: either "str" or "dict", the representation of the trap spaces

    **returns**:
        * *subspaces*: the trap spaces

    **example**::

        >>> bnet = ["x, !x | y | z",
        ...         "y, !x&z | y&!z",
        ...         "z, x&y | z"]
        >>> bnet = "\\n".join(bnet)
        >>> primes = bnet2primes(bnet)
        >>> tspaces = trap_spaces(primes, "all", representation="str")
        ---, --1, 1-1, -00, 101
    """
    
    # exclude trivial trap space {} for search of maximal trap spaces
    Bounds = None
    if option == "max":
        Bounds = (1, "n")
    
    return potassco_handle(primes, option, bounds=Bounds, project=None, max_output=max_output, fname_asp=fname_asp,
                           representation=representation)


def steady_states(primes: dict, max_output: int = 1000, fname_asp: Optional[str] = None, representation: str = "dict") -> Union[List[dict], List[str]]:
    """
    Returns steady states.

    **arguments**:
        * *primes*: prime implicants
        * *max_output*: maximal number of trap spaces to return
        * *fname_asp*: file name or *None*
        * *representation*: either "str" or "dict", the representation of the trap spaces

    **returns**:
        * *states*: the steady states

    **example**::

        >>> steady = steady_states(primes)
        >>> len(steady)
        2
    """
    
    return potassco_handle(primes, type_="all", bounds=("n", "n"), project=[], max_output=max_output, fname_asp=fname_asp, representation=representation)


def trap_spaces_bounded(primes: dict, type_: str, bounds: tuple, max_output: int = 1000, fname_asp: Optional[str] = None):
    """
    Returns a list of bounded trap spaces using the Potassco_ ASP solver :ref:`[Gebser2011]<Gebser2011>`.
    See :ref:`trap_spaces <sec:trap_spaces>` for details of the parameters *type_*, *max_output* and *fname_asp*.
    The parameter *bounds* is used to restrict the set of trap spaces from which maximal, minimal or all solutions are drawn
    to those whose number of fixed variables are within the given range.
    Example: ``bounds=(5,8)`` instructs Potassco_ to consider only trap spaces with 5 to 8 fixed variables as feasible.
    *type_* selects minimal, maximal or all trap spaces from the restricted set.
    .. warning::
        The *Bound* constraint is applied *before* selecting minimal or maximal trap spaces.
        A trap space may therefore be minimal w.r.t. to certain bounds but not minimal in the unbounded sense.

    Use ``"n"`` as a shortcut for "all variables", i.e., instead of ``len(primes)``.
    Example: Use ``bounds=("n","n")`` to compute steady states.
    Note that the parameter *type_* becomes irrelevant for ``bounds=(x,y)`` with ``x=y``.

    **arguments**:
        * *primes*: prime implicants
        * *type_* in ``["max","min","all"]``: subset minimal, subset maximal or all solutions
        * *bounds*: the upper and lower bound for the number of fixed variables
        * *max_output*: maximal number of trap spaces to return
        * *fname_asp*: file name or *None*
    **returns**:
        * list of trap spaces
    **example**::
        >>> tspaces = trap_spaces_bounded(primes, "min", (2,4))
        >>> len(tspaces)
        12
        >>> tspaces[0]
        {'TGFR':0,'FGFR':0}
    """
    
    return potassco_handle(primes, type_, bounds, project=None, max_output=max_output, fname_asp=fname_asp, representation="dict")


def steady_states_projected(primes: dict, project, max_output: int = 1000, fname_asp: Optional[str] = None):
    """
    Returns a list of projected steady states using the Potassco_ ASP solver :ref:`[Gebser2011]<Gebser2011>`.

    **arguments**:
        * *primes*: prime implicants
        * *project*: list of names
        * *max_output*: maximal number of trap spaces to return
        * *fname_asp*: file name or *None*

    **returns**:
        * *Activities*: projected steady states

    **example**::

        >>> psteady = steady_states_projected(primes, ["v1","v2"])
        >>> len(psteady)
        2
        >>> psteady
        [{"v1":1,"v2":0},{"v1":0,"v2":0}]
    """

    unknown_names = set(project).difference(set(primes))
    if unknown_names:
        log.error(f"can not project steady states: unknown_names={unknown_names}")
        sys.exit()
    
    return potassco_handle(primes, type_="all", bounds=("n", "n"), project=project, max_output=max_output, fname_asp=fname_asp, representation="dict")


def primes2asp(primes: dict, fname_asp: str, bounds: Optional[tuple], project, type_: str, extra_lines: Optional[List[str]] = None):
    """
    Saves Primes as an *asp* file in the Potassco_ format intended for computing minimal and maximal trap spaces.
    The homepage of the Potassco_ solving collection is http://potassco.sourceforge.net.
    The *asp* file consists of data, the hyperarcs of the prime implicant graph,
    and a problem description that includes the consistency, stability and non-emptiness conditions.

    There are four additional parameters that modify the problem:

    *bounds* must be either a tuple of integers *(a,b)* or *None*.
    A tuple *(a,b)* uses Potassco_'s cardinality constraints to enforce that the number of fixed variables *x* of a trap space satisfies *a<=x<=b*.
    *None* results in no bounds.

    *project* must be either a list of names or *None*.
    A list of names projects the solutions onto these variables using the meta command "#show" and the clasp parameter "--project".
    Variables of *project* that do not appear in *primes* are ignored.
    *None* results in no projection.

    *type_* specifies whether additional constraints should be enforced.
    For example for computing circuits or percolated trap spaces.
    Recognized values are 'circuits' and 'percolated', everything else will be ignored.

    **arguments**:
       * *primes*: prime implicants
       * *fname_asp*: name of *ASP* file or None
       * *bounds*: cardinality constraint for the number of fixed variables
       * *project*: names to project to or *None* for no projection
       * *type_*: one of 'max', 'min', 'all', 'percolated', 'circuits' or *None*

    **returns**:
       * *asp_text*: contents of asp file

    **example**::

          >>> primes2asp(primes, "mapk.asp", False, False)
          >>> primes2asp(primes, "mapk_bounded.asp", (20,30), False)
          >>> primes2asp(primes, "mapk_projected.asp", False, ["AKT","GADD45","FOS","SMAD"])
    """

    assert type_ in [None, "max", "min", "all", "percolated", "circuits"]
    assert fname_asp is None or type(fname_asp) == str
    assert bounds is None or type(bounds) == tuple
    assert project is None or type(project) == list
    
    if project:
        project = [x for x in project if x in primes]
    
    lines = ['%% created on %s using PyBoolNet' % datetime.date.today().strftime('%d. %b. %Y'),
             '% PyBoolNet is available at https://github.com/hklarner/PyBoolNet',
             '',
             '% encoding of prime implicants as hyper-arcs that consist of a unique "target" and (possibly) several "sources".',
             '% "target" and "source" are triplets that consist of a variable name, an activity and a unique arc-identifier. ',
             '']
    
    index = 0
    for name in sorted(primes.keys()):
        for value in [0, 1]:
            for p in primes[name][value]:
                index += 1
                hyper = [f'target("{name}",{value},a{index}).']
                for n2, v2 in p.items():
                    hyper.append(f'source("{n2}",{v2},a{index}).')
                lines += [" ".join(hyper)]
    
    lines += [""]
    lines += [
        '% generator: "in_set(ID)" specifies which arcs are chosen for a trap set (ID is unique for target(_,_,_)).',
        '{in_set(ID) : target(V,S,ID)}.',
        '',
        '% consistency constraint',
        ':- in_set(ID1), in_set(ID2), target(V,1,ID1), target(V,0,ID2).',
        '',
        '% stability constraint',
        ':- in_set(ID1), source(V,S,ID1), not in_set(ID2) : target(V,S,ID2).',
        '']
    
    if type_ in ['percolated', 'circuits']:
        lines += [
            '% percolation constraint.',
            '% ensure that if all sources of a prime are hit then it must belong to the solution.',
            'in_set(ID) :- target(V,S,ID), hit(V1,S1) : source(V1,S1,ID).']
    else:
        lines += [
            '% bijection constraint (between asp solutions and trap spaces)',
            '% to avoid the repetition of equivalent solutions we add all prime implicants',
            '% that agree with the current solution.',
            'in_set(ID) :- target(V,S,ID), hit(V,S), hit(V1,S1) : source(V1,S1,ID).']
    
    if type_ == 'circuits':
        lines += ['',
                  '% circuits constraint, distinguishes between circuit nodes and percolated nodes',
                  'upstream(V1,V2) :- in_set(ID), target(V1,S1,ID), source(V2,S2,ID).',
                  'upstream(V1,V2) :- upstream(V1,V3), upstream(V3,V2).',
                  'percolated(V1) :- hit(V1,S), not upstream(V1,V1).']
    
    lines += ['',
              '% "hit" captures the stable variables and their activities.',
              'hit(V,S) :- in_set(ID), target(V,S,ID).']
    
    if bounds:
        lines += ['',
                  '%% cardinality constraint (enforced by "Bounds=%s")' % repr(bounds), ]
        if bounds[0] > 0:
            lines += [':- {hit(V,S)} %i.' % (bounds[0] - 1)]
        lines += [':- %i {hit(V,S)}.' % (bounds[1] + 1)]
    
    if extra_lines:
        lines += extra_lines
    
    if project:
        lines += ['', '%% show projection (enforced by "Project=%s").' % (repr(sorted(project)))]
        lines += ['#show.']
        lines += ['#show hit("{n}",S) : hit("{n}",S).'.format(n=name) for name in project]
    
    elif type_ == 'circuits':
        lines += ['',
                  '% show fixed nodes and distinguish between circuits and percolated',
                  '#show percolated/1.',
                  '#show hit/2.']
    
    else:
        lines += ['',
                  '% show fixed nodes',
                  '#show hit/2.']

    asp_text = "\n".join(lines)
    
    with open(fname_asp, "w") as f:
        f.write(asp_text)

    log.info(f"created {fname_asp}")
    return asp_text


def potassco_handle(primes: dict, type_: str, bounds: tuple, project, max_output: int, fname_asp: str, representation: str, extra_lines=None):
    """
    Returns a list of trap spaces using the Potassco_ ASP solver :ref:`[Gebser2011]<Gebser2011>`.
    """

    if type_ not in ["max", "min", "all", "percolated", "circuits"]:
        log.error(f"unknown trap space type: type={type_}")
        sys.exit()

    if representation not in ["str", "dict"]:
        log.error(f"unknown trap space representation: representation={representation}")
        sys.exit()
    
    if bounds:
        bounds = tuple([len(primes) if x == "n" else x for x in bounds])

    params_clasp = ["--project"]
    
    if type_ == "max":
        params_clasp += ["--enum-mode=domRec", "--heuristic=Domain", "--dom-mod=5,16"]

    elif type_ == "min":
        params_clasp += ["--enum-mode=domRec", "--heuristic=Domain", "--dom-mod=3,16"]
    
    asp_text = primes2asp(primes=primes, fname_asp=fname_asp, bounds=bounds, project=project, type_=type_, extra_lines=extra_lines)
    
    try:
        if fname_asp is None:
            cmd_gringo = [CMD_GRINGO]
            proc_gringo = subprocess.Popen(cmd_gringo, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cmd_clasp = [CMD_CLASP, '--models=%i' % max_output] + params_clasp
            proc_clasp = subprocess.Popen(cmd_clasp, stdin=proc_gringo.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            proc_gringo.stdin.write(asp_text.encode())
            proc_gringo.stdin.close()
            
            output, error = proc_clasp.communicate()
            error = error.decode()
            output = output.decode()
        
        else:
            cmd_gringo = [CMD_GRINGO, fname_asp]
            proc_gringo = subprocess.Popen(cmd_gringo, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cmd_clasp = [CMD_CLASP, '--models=%i' % max_output] + params_clasp
            proc_clasp = subprocess.Popen(cmd_clasp, stdin=proc_gringo.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            output, error = proc_clasp.communicate()
            error = error.decode()
            output = output.decode()
    
    except Exception as e:
        log.error(asp_text)
        log.error(e)
        log.error("Call to gringo and / or clasp failed.")
        
        if fname_asp is not None:
            log.info(f'command: {" ".join(cmd_gringo + ["|"] + cmd_clasp)}')
        
        raise e
    
    if "ERROR" in error:
        log.error("Call to gringo and / or clasp failed.")
        if fname_asp is not None:
            log.error(f"asp file: {asp_text}")
        log.error(f"command: {' '.join(cmd_gringo + ['|'] + cmd_clasp)}")
        log.error(f"error: {error}")
        sys.exit()
    
    log.debug(asp_text)
    log.debug(f"cmd_gringo={' '.join(cmd_gringo)}")
    log.debug(f"cmd_clasp={' '.join(cmd_clasp)}")
    log.debug(error)
    log.debug(output)
    
    lines = output.split("\n")
    result = []

    if type_ == "circuits":
        while lines and len(result) < max_output:
            line = lines.pop(0)
            
            if line[:6] == "Answer":
                line = lines.pop(0)
                
                tspace = [x for x in line.split() if "hit" in x]
                tspace = [x[4:-1].split(",") for x in tspace]
                tspace = [(x[0][1:-1], int(x[1])) for x in tspace]
                
                perc = [x[12:-2] for x in line.split() if "perc" in x]
                perc = [x for x in tspace if x[0] in perc]
                perc = dict(perc)
                
                circ = [x for x in tspace if x[0] not in perc]
                circ = dict(circ)
                
                result.append((circ, perc))

    else:
        while lines and len(result) < max_output:
            line = lines.pop(0)
            
            if line[:6] == "Answer":
                line = lines.pop(0)
                d = [x[4:-1].split(",") for x in line.split()]
                d = [(x[0][1:-1], int(x[1])) for x in d]
                result.append(dict(d))
    
    if len(result) == max_output:
        log.info(f"There are possibly more than {max_output} trap spaces.")
        log.info("Increase MaxOutput to find out.")
    
    if representation == "str":
        if type_ == "circuits":
            result = [(subspace2str(primes, x), subspace2str(primes, y)) for x, y in result]
        else:
            result = [subspace2str(primes, x) for x in result]
    
    return result


