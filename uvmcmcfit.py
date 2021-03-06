#!/usr/bin/env python
"""
 Author: Shane Bussmann

 Last modified: 2014 February 26

 Note: This is experimental software that is in a very active stage of
 development.  If you are interested in using this for your research, please
 contact me first at sbussmann@astro.cornell.edu!  Thanks.

 Purpose: Fit a parametric model to interferometric data using Dan
 Foreman-Mackey's emcee routine.  Gravitationally lensed sources are accounted
 for using ray-tracing routines based on Adam Bolton's lensdemo_script and
 lensdemo_func python scripts.  Here is the copyright license from
 lensdemo_script.py:

 Copyright 2009 by Adam S. Bolton
 Creative Commons Attribution-Noncommercial-ShareAlike 3.0 license applies:
 http://creativecommons.org/licenses/by-nc-sa/3.0/
 All redistributions, modified or otherwise, must include this
 original copyright notice, licensing statement, and disclaimer.
 DISCLAIMER: ABSOLUTELY NO WARRANTY EXPRESS OR IMPLIED.
 AUTHOR ASSUMES NO LIABILITY IN CONNECTION WITH THIS COMPUTER CODE.

--------------------------
 USAGE

 python $PYSRC/uvmcmcfit.py

--------------------------
 SETUP PROCEDURES

 1. Establish a directory that contains data for the specific target for which
 you wish to measure a lens model.  This is the directory from which you will
 run the software.

 I call this "uvfit00" for the first run on a given dataset, "uvfit01" for
 the second, etc.

 2. Inside this directory, you must ensure the following files are present:

 - "config.py": This is the configuration file that describes where the source
 of interest is located, what type of model to use for the lens and source, the
 name of the image of the target from your interferometric data, the name of
 the uvfits files containing the interferometric visibilities, and a few
 important processing options as well.  Syntax is python.

 - Image of the target from your interferometric data.  The spatial resolution
 of this image (arcseconds per pixel), modified by an optional oversampling
 parameter, defines the spatial resolution in both the unlensed and lensed
 surface brightness maps.

 - interferometric visibilities for every combination of array configuration,
 sideband, and date observed that you want to model.  

 3. More info about the constraints and priors input files.

 - Lenses: The lenses are assumed to have singular isothermal ellipsoid
 profiles.  

 - Sources: Sources are represented by Gaussian profiles.  Source positions are
 always defined relative to the primary lens, unless there is no lens, in which
 case they are defined relative to the emission centroid defined in
 "config.txt."

--------
 OUTPUTS

 "posteriorpdf.hdf5": model parameters for every MCMC iteration, in hdf5
 format.  Google search for hdf5 view if you want a tool to inspect the hdf5
 files directly.

"""

# import the required modules
import os
import os.path
import sys
from astropy.io import fits
from astropy.io.misc import hdf5
import numpy
from astropy.table import Table
import emcee
from emcee.utils import MPIPool
#import pyximport
#pyximport.install(setup_args={"include_dirs":numpy.get_include()})
import sample_vis
import lensutil
import uvutil


cwd = os.getcwd()
sys.path.append(cwd)
import config


# the function that computes the ln-probabilities
def lnprob(pzero_regions, p_u_regions, p_l_regions, fixindx, \
        real, imag, wgt, uuu, vvv, pcd, lnlikemethod, \
        x_regions, y_regions, headmod_regions, celldata, \
        model_types_regions, nregions, nlens_regions, nsource_regions):

    # impose constraints on parameters by setting chi^2 to enormously high
    # value when a walker chooses a parameter outside the constraints
    if (pzero_regions < p_l_regions).any():
        probln = -numpy.inf
        mu_flux = 0
        #print probln, mu_flux, pzero
        #print probln, ["%0.2f" % i for i in pzero]
        return probln, mu_flux
    if (pzero_regions > p_u_regions).any():
        probln = -numpy.inf
        mu_flux = 0
        #print probln, ["%0.2f" % i for i in pzero]
        return probln, mu_flux
    if (pzero_regions * 0 != 0).any():
        probln = -numpy.inf
        mu_flux = 0
        #print probln, ["%0.2f" % i for i in pzero]
        return probln, mu_flux

    # search poff_models for parameters fixed relative to other parameters
    fixed = (numpy.where(fixindx >= 0))[0]
    nfixed = fixindx[fixed].size
    poff_regions = p_u_regions.copy()
    poff_regions[:] = 0.
    for ifix in range(nfixed):
        poff_regions[fixed[ifix]] = pzero_regions[fixindx[fixed[ifix]]]

    parameters_regions = pzero_regions + poff_regions

    model_real = 0.
    model_imag = 0.
    npar_previous = 0
    prindx = 0

    amp = []

    for regioni in range(nregions):

        # get the model info for this model
        x = x_regions[regioni]
        y = y_regions[regioni]
        headmod = headmod_regions[regioni]
        nlens = nlens_regions[regioni]
        nsource = nsource_regions[regioni]
        model_types = model_types_regions[prindx:prindx + nsource]
        prindx += nsource
        #model_types_regioni = model_types[regioni]

        # get pzero, p_u, and p_l for this specific model
        nparlens = 5 * nlens
        nparsource = 6 * nsource
        npar = nparlens + nparsource + npar_previous
        parameters = parameters_regions[npar_previous:npar]
        npar_previous += npar

        #-----------------------------------------------------------------
        # Create a surface brightness map of lensed emission for the given set
        # of foreground lens(es) and background source parameters.
        #-----------------------------------------------------------------

        g_image, g_lensimage, e_image, e_lensimage, amp_tot, amp_mask = \
                lensutil.sbmap(x, y, nlens, nsource, parameters, model_types)
        amp.extend(amp_tot)
        amp.extend(amp_mask)

        #----------------------------------------------------------------------
        # Python version of UVMODEL:
        # "Observe" the lensed emission with the interferometer
        #----------------------------------------------------------------------

        if nlens > 0:
            # Evaluate amplification for each region
            lensmask = e_lensimage != 0
            mask = e_image != 0
            numer = g_lensimage[lensmask].sum()
            denom = g_image[mask].sum()
            amp_mask = numer / denom
            numer = g_lensimage.sum()
            denom = g_image.sum()
            amp_tot = numer / denom
            if amp_tot > 1e2:
                amp_tot = 1e2
            if amp_mask > 1e2:
                amp_mask = 1e2
            amp.extend([amp_tot])
            amp.extend([amp_mask])

        model_complex = sample_vis.uvmodel(g_image, headmod, uuu, vvv, pcd)
        model_real += numpy.real(model_complex)
        model_imag += numpy.imag(model_complex)

        #fits.writeto('g_lensimage.fits', g_lensimage, headmod, clobber=True)
        #import matplotlib.pyplot as plt
        #print pzero_regions
        #plt.imshow(g_lensimage, origin='lower')
        #plt.colorbar()
        #plt.show()

    # use all visibilities
    goodvis = (real * 0 == 0)

    # calculate chi^2 assuming natural weighting
    #fnuisance = 0.0
    modvariance_real = 1 / wgt #+ fnuisance ** 2 * model_real ** 2
    modvariance_imag = 1 / wgt #+ fnuisance ** 2 * model_imag ** 2
    #wgt = wgt / 4.
    chi2_real_all = (real - model_real) ** 2. / modvariance_real
    chi2_imag_all = (imag - model_imag) ** 2. / modvariance_imag
    chi2_all = numpy.append(chi2_real_all, chi2_imag_all)

    # compute the sigma term
    sigmaterm_real = numpy.log(2 * numpy.pi * modvariance_real)
    sigmaterm_imag = numpy.log(2 * numpy.pi * modvariance_imag)
    sigmaterm_all = numpy.append(sigmaterm_real, sigmaterm_imag)

    # compute the ln likelihood
    if lnlikemethod == 'chi2':
        lnlike = chi2_all
    else:
        lnlike = chi2_all + sigmaterm_all

    # compute number of degrees of freedom
    #nmeasure = lnlike.size
    #nparam = (pzero != 0).size
    #ndof = nmeasure - nparam

    # assert that lnprob is equal to -1 * maximum likelihood estimate
    probln = -0.5 * lnlike[goodvis].sum()
    if probln * 0 != 0:
        probln = -numpy.inf
    #print ndof, probln, sigmaterm_all.sum(), chi2_all.sum()

    return probln, amp

# Determine parallel processing options
mpi = config.ParallelProcessingMode

# Single processor with Nthreads cores
if mpi != 'MPI':

    # set the number of threads to use for parallel processing
    Nthreads = config.Nthreads

# multiple processors on a cluster using MPI
else:

    # One thread per slot
    Nthreads = 1

    # Initialize the pool object
    pool = MPIPool()

    # If this process is not running as master, wait for instructions, then exit
    if not pool.is_master():
        pool.wait()
        sys.exit(0)

#--------------------------------------------------------------------------
# Read in ALMA image and beam
im = fits.getdata(config.ImageName)
im = im[0, 0, :, :].copy()
headim = fits.getheader(config.ImageName)

# get resolution in ALMA image
celldata = numpy.abs(headim['CDELT1'] * 3600)

#--------------------------------------------------------------------------
# read in visibilities
fitsfiles = config.FitsFiles
nfiles = len(fitsfiles)
nvis = []

# read in the observed visibilities
uuu = []
vvv = []
real = []
imag = []
wgt = []
for file in fitsfiles:
    print file
    vis_data = fits.open(file)

    uu, vv = uvutil.uvload(vis_data)
    pcd = uvutil.pcdload(vis_data)
    real_raw, imag_raw, wgt_raw = uvutil.visload(vis_data)
    uuu.extend(uu)
    vvv.extend(vv)
    real.extend(real_raw)
    imag.extend(imag_raw)
    wgt.extend(wgt_raw)

# convert the list to an array
real = numpy.array(real)
imag = numpy.array(imag)
wgt = numpy.array(wgt)
uuu = numpy.array(uuu)
vvv = numpy.array(vvv)
#www = numpy.array(www)

# remove the data points with zero or negative weight
positive_definite = wgt > 0
real = real[positive_definite]
imag = imag[positive_definite]
wgt = wgt[positive_definite]
uuu = uuu[positive_definite]
vvv = vvv[positive_definite]
#www = www[positive_definite]

npos = wgt.size

#----------------------------------------------------------------------------
# Define the number of walkers
nwalkers = 32

# determine the number of regions for which we need surface brightness maps
regionIDs = config.RegionID
nregions = len(regionIDs)

# instantiate lists that must be carried through to lnprob function
x = []
y = []
modelheader = []
x_l_off = []
y_l_off = []
nlens_regions = []
nsource_regions = []
p_u = []
p_l = []
poff = []
pname = []
pzero = []
model_types = []
previousndim_model = 0
previousnmu = 0
for i in range(nregions):
    ri = str(i)
    ra_centroid = config.RACentroid[i]
    dec_centroid = config.DecCentroid[i]
    extent = config.RadialExtent[i]
    oversample = config.Oversample[i]
    nlens = config.Nlens[i]
    nsource = config.Nsource[i]

    # Append the number of lenses and sources for this region
    nlens_regions.append(nlens)
    nsource_regions.append(nsource)

    # define number of pixels in lensed surface brightness map
    dx = 2 * extent
    nxmod = oversample * int(round(dx / celldata))
    dy = 2 * extent
    nymod = oversample * int(round(dy / celldata))

    # make x and y coordinate images for lens model
    onex = numpy.ones(nxmod)
    oney = numpy.ones(nymod)
    linspacex = numpy.linspace(0, 1, nxmod)
    linspacey = numpy.linspace(0, 1, nymod)
    x.append(dx * numpy.outer(oney, linspacex) - extent)
    y.append(dy * numpy.outer(linspacey, onex) - extent)

    # Provide world-coordinate system transformation data in the header of
    # the lensed surface brightness map
    headmod = headim.copy()
    crpix1 = nxmod / 2 + 1
    crpix2 = nymod / 2 + 1
    cdelt1 = -1 * celldata / 3600 / oversample
    cdelt2 = celldata / 3600 / oversample
    headmod.update('naxis1', nxmod)
    headmod.update('cdelt1', cdelt1)
    headmod.update('crpix1', crpix1)
    headmod.update('crval1', ra_centroid)
    headmod.update('ctype1', 'RA---SIN')
    headmod.update('naxis2', nymod)
    headmod.update('cdelt2', cdelt2)
    headmod.update('crpix2', crpix2)
    headmod.update('crval2', dec_centroid)
    headmod.update('ctype2', 'DEC--SIN')
    modelheader.append(headmod)

    # the parameter initialization vectors
    p1 = []
    p2 = []

    for ilens in range(nlens):

        li = str(ilens)

        # constraints on the lenses
        lensparams = ['EinsteinRadius', 'DeltaRA', 'DeltaDec', 'AxialRatio', \
                'PositionAngle']
        tag = '_Lens' + li + '_Region' + ri
        for lensparam in lensparams:
            fullparname = 'Constraint_' + lensparam + tag
            values = getattr(config, fullparname)
            poff.append(values.pop()) 
            values = numpy.array(values).astype(float)
            p_u.append(values[1]) 
            p_l.append(values[0]) 
            pname.append(lensparam + tag)
            fullparname = 'Init_' + lensparam + tag
            values = getattr(config, fullparname)
            p2.append(values[1]) 
            p1.append(values[0]) 

    for isource in range(nsource):

        si = str(isource)

        sourceparams = ['IntrinsicFlux', 'Size', 'DeltaRA', 'DeltaDec', \
                'AxialRatio', 'PositionAngle']
        tag = '_Source' + si + '_Region' + ri
        for sourceparam in sourceparams:
            fullparname = 'Constraint_' + sourceparam + tag
            values = getattr(config, fullparname)
            poff.append(values.pop()) 
            values = numpy.array(values).astype(float)
            p_u.append(values[1]) 
            p_l.append(values[0]) 
            pname.append(sourceparam + tag)
            fullparname = 'Init_' + sourceparam + tag
            values = getattr(config, fullparname)
            p2.append(values[1]) 
            p1.append(values[0]) 

        # get the model type
        fullparname = 'ModelMorphology' + tag
        model_types.append(getattr(config, fullparname))

    # determine the number of free parameters in the model
    nparams = len(p1)

    # Otherwise, choose an initial set of positions for the walkers.
    pzero_model = numpy.zeros((nwalkers, nparams))
    for j in xrange(nparams):
        #if p3[j] == 'uniform':
        pzero_model[:, j] = numpy.random.uniform(p1[j], p2[j], nwalkers)
        #if p3[j] == 'normal':
        #    pzero_model[:,j] = (numpy.random.normal(loc=p1[j], 
        #    scale=p2[j], size=nwalkers))
        #if p4[j] == 'pos':
        #    pzero[:, j] = numpy.abs(pzero[:, j])
    if pzero == []:
        pzero = pzero_model
    else:
        pzero = numpy.append(pzero, pzero_model, axis=1)

# Use an intermediate posterior PDF to initialize the walkers if it exists
posteriorloc = 'posteriorpdf.hdf5'
if os.path.exists(posteriorloc):

    # read the latest posterior PDFs
    print "Found existing posterior PDF file: " + posteriorloc
    posteriordat = hdf5.read_table_hdf5(posteriorloc)
    if len(posteriordat) > 1:

        # assign values to pzero
        nlnprob = 1
        pzero = numpy.zeros((nwalkers, nparams))
        startindx = nlnprob #+ previousndim_model
        for j in range(nparams):
            namej = posteriordat.colnames[j + startindx]
            pzero[:, j] = posteriordat[namej][-nwalkers:]

        # output name is based on most recent burnin file name
        realpdf = True
    else:
        realpdf = False
else:
    realpdf = False

if not realpdf:
    extendedpname = ['lnprob']
    extendedpname.extend(pname)
    nmu = 0
    for regioni in range(nregions):
        ri = str(regioni)
        if nlens_regions[regioni] > 0:
            for i in range(nsource):
                si = '.Source' + str(i) + '.Region' + ri
                extendedpname.append('mu_tot' + si) 
                extendedpname.append('mu_aper' + si) 
                nmu += 2
            extendedpname.append('mu_tot.Region' + ri)
            extendedpname.append('mu_aper.Region' + ri) 
            nmu += 2
    posteriordat = Table(names = extendedpname)

# make sure no parts of pzero exceed p_u or p_l
arrayp_u = numpy.array(p_u)
arrayp_l = numpy.array(p_l)
arraypzero = numpy.array(pzero)
for j in xrange(nwalkers):
    exceed = arraypzero[j] >= arrayp_u
    arraypzero[j, exceed] = 2 * arrayp_u[exceed] - arraypzero[j, exceed]
    exceed = arraypzero[j] <= arrayp_l
    arraypzero[j, exceed] = 2 * arrayp_l[exceed] - arraypzero[j, exceed]
pzero = arraypzero
p_u = arrayp_u
p_l = arrayp_l

# determine the indices for fixed parameters
fixindx = numpy.zeros(nparams) - 1
for ifix in range(nparams):
    if pname.count(poff[ifix]) > 0:
        fixindx[ifix] = pname.index(poff[ifix])

# Determine method of computing lnlike
lnlikemethod = config.lnLike

# Initialize the sampler with the chosen specs.
if mpi != 'MPI':
    # Single processor with Nthreads cores
    sampler = emcee.EnsembleSampler(nwalkers, nparams, lnprob, \
        args=[p_u, p_l, fixindx, real, imag, wgt, uuu, vvv, pcd, \
        lnlikemethod, x, y, modelheader, celldata, model_types, nregions, \
        nlens_regions, nsource_regions], threads=Nthreads)
else:
    # Multiple processors using MPI
    sampler = emcee.EnsembleSampler(nwalkers, nparams, lnprob, pool=pool, \
        args=[p_u, p_l, fixindx, real, imag, wgt, uuu, vvv, pcd, \
        lnlikemethod, x, y, modelheader, celldata, model_types, nregions, \
        nlens_regions, nsource_regions])

# Sample, outputting to a file
os.system('date')

for pos, prob, state, amp in sampler.sample(pzero, iterations=10000):

    print numpy.mean(sampler.acceptance_fraction)
    print os.system('date')
    #ff.write(str(prob))
    yesamp = amp > 0
    namp = len(amp[yesamp])
    superpos = numpy.zeros(1 + nparams + namp)
    for wi in range(nwalkers):
        superpos[0] = prob[wi]
        superpos[1:nparams + 1] = pos[wi]
        superpos[nparams + 1:nparams + namp + 1] = amp[wi]
        posteriordat.add_row(superpos)
    hdf5.write_table_hdf5(posteriordat, 'posteriorpdf.hdf5', 
            path = '/posteriorpdf', overwrite=True, compression=True)
