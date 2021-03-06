"""
2014 January 31
Shane Bussmann

Varius utilities related to operations on uvfits data files.
"""

import numpy
from astropy.io import fits

def pcdload(visfile):

    # read in the uvfits data
    visheader = visfile[0].header

    # identify the telescope
    telescop = visheader['TELESCOP']

    if telescop == 'ALMA':

        # identify the phase center
        pcd_ra = visfile['AIPS SU '].data['RAEPO'][0]
        pcd_dec = visfile['AIPS SU '].data['DECEPO'][0]
        pcd = [pcd_ra, pcd_dec]
        return pcd

    if telescop == 'PdBI':

       # identify the channel frequency(ies):
        pcd_ra = visfile[0].header['OBSRA']
        pcd_dec = visfile[0].header['OBSDEC']
        pcd = [pcd_ra, pcd_dec]
        return pcd

def uvload(visfile):

    # read in the uvfits data
    #visfile = fits.open(visdataloc)
    visibilities = visfile[0].data
    visheader = visfile[0].header

    # identify the telescope
    telescop = visheader['TELESCOP']

    if telescop == 'ALMA':

        # identify the channel frequency(ies):
        visfreq = visfile[1].data
        freq0 = visheader['CRVAL4']
        dfreq = visheader['CDELT4']
        cfreq = visheader['CRPIX4']
        nvis = visibilities['DATA'][:, 0, 0, 0, 0, 0, 0].size
        nspw = visibilities['DATA'][0, 0, 0, :, 0, 0, 0].size
        nfreq = visibilities['DATA'][0, 0, 0, 0, :, 0, 0].size
        npol = visibilities['DATA'][0, 0, 0, 0, 0, :, 0].size
        uu = numpy.zeros([nvis, nspw, nfreq, npol])
        vv = numpy.zeros([nvis, nspw, nfreq, npol])
        #wgt = numpy.zeros([nvis, nspw, nfreq, npol])

        for ispw in range(nspw):
            if nspw > 1:
                freqif = freq0 + visfreq['IF FREQ'][0][ispw]
            else:
                freqif = freq0
            #uu[:, ispw] = freqif * visibilities['UU']
            #vv[:, ispw] = freqif * visibilities['VV']

            for ipol in range(npol):

                # then compute the spatial frequencies:
                if nfreq > 1:
                    freq = (numpy.arange(nfreq) - cfreq + 1) * dfreq + freqif
                    freqvis = numpy.meshgrid(freq, visibilities['UU'])
                    uu[:, ispw, :, ipol] = freqvis[0] * freqvis[1]
                    freqvis = numpy.meshgrid(freq, visibilities['VV'])
                    vv[:, ispw, :, ipol] = freqvis[0] * freqvis[1]
                else:
                    uu[:, ispw, 0, ipol] = freqif * visibilities['UU']
                    vv[:, ispw, 0, ipol] = freqif * visibilities['VV']

    if telescop == 'PdBI':

        # identify the channel frequency(ies):
        freq0 = visheader['CRVAL4']
        dfreq = visheader['CDELT4']
        cfreq = visheader['CRPIX4']
        nvis = visibilities['DATA'][:, 0, 0, 0, 0, 0].size
        nfreq = visibilities['DATA'][0, 0, 0, :, 0, 0].size
        npol = visibilities['DATA'][0, 0, 0, 0, :, 0].size
        uu = numpy.zeros([nvis, nfreq, npol])
        vv = numpy.zeros([nvis, nfreq, npol])
        #wgt = numpy.zeros([nvis, nspw, nfreq, npol])

        freqif = freq0
        #uu[:, ispw] = freqif * visibilities['UU']
        #vv[:, ispw] = freqif * visibilities['VV']

        for ipol in range(npol):

            # then compute the spatial frequencies:
            if nfreq > 1:
                freq = (numpy.arange(nfreq) - cfreq + 1) * dfreq + freqif
                freqvis = numpy.meshgrid(freq, visibilities['UU'])
                uu[:, :, ipol] = freqvis[0] * freqvis[1]
                freqvis = numpy.meshgrid(freq, visibilities['VV'])
                vv[:, :, ipol] = freqvis[0] * freqvis[1]
            else:
                uu[:, 0, ipol] = freqif * visibilities['UU']
                vv[:, 0, ipol] = freqif * visibilities['VV']
                #www = freqif * visibilities['WW']

    return uu, vv

def visload(visfile):
    # get the telescope name
    visheader = visfile[0].header
    #telescop = visheader['TELESCOP']

    # if we are dealing with SMA data
    if visheader['NAXIS'] == 6:
        data_real = visfile[0].data['DATA'][:,0,0,:,:,0]
        data_imag = visfile[0].data['DATA'][:,0,0,:,:,1]
        data_wgt = visfile[0].data['DATA'][:,0,0,:,:,2]

    # if we are dealing with ALMA data
    if visheader['NAXIS'] == 7:
        data_real = visfile[0].data['DATA'][:,0,0,:,:,:,0]
        data_imag = visfile[0].data['DATA'][:,0,0,:,:,:,1]
        data_wgt = visfile[0].data['DATA'][:,0,0,:,:,:,2]

    return data_real, data_imag, data_wgt

def statwt(visdataloc, newvisdataloc):

    visfile = fits.open(visdataloc)
    data_real, data_imag, data_wgt = visload(visfile)

    # get the number of visibilities, spws, frequencies, polarizations
    if data_real.ndim == 4:
        nvis = data_real[:, 0, 0, 0].size
        nspw = data_real[0, :, 0, 0].size
        nfreq = data_real[0, 0, :, 0].size
        npol = data_real[0, 0, 0, :].size
        wgt = numpy.zeros([nvis, nspw, nfreq, npol])
    if data_real.ndim == 3:
        nvis = data_real[:, 0, 0].size
        nspw = 0
        nfreq = data_real[0, :, 0].size
        npol = data_real[0, 0, :].size
        wgt = numpy.zeros([nvis, nfreq, npol])

    if nspw > 0:
        for ispw in range(nspw):

            for ipol in range(npol):

                # compute real and imaginary components of the visibilities
                real_raw = data_real[:, ispw, :, ipol]
                imag_raw = data_imag[:, ispw, :, ipol]
                wgt_raw = data_wgt[:, ispw, :, ipol]

                # derive the weights directly from the data
                freqsize = real_raw[0, :].size
                wgt_scaled = numpy.zeros([nvis, freqsize])
                for i in range(nvis):
                    gwgt = wgt_raw[i, :] > 0
                    ngwgt = wgt_raw[i, gwgt].size
                    if ngwgt > 2:
                        reali = real_raw[i, gwgt]
                        imagi = imag_raw[i, gwgt]
                        rms_real = numpy.std(reali)
                        rms_imag = numpy.std(imagi)
                        rms_avg = (rms_real + rms_imag) / 2.
                        wgt_scaled[i, gwgt] = 1 / rms_avg ** 2
                wgt[:, ispw, :, ipol] = wgt_scaled
        visfile[0].data['DATA'][:, 0, 0, :, :, :, 2] = wgt
    else:

        for ipol in range(npol):

            # compute real and imaginary components of the visibilities
            real_raw = data_real[:, :, ipol]
            imag_raw = data_imag[:, :, ipol]
            wgt_raw = data_wgt[:, :, ipol]

            # derive the weights directly from the data
            freqsize = real_raw[0, :].size
            wgt_scaled = numpy.zeros([nvis, freqsize])
            for i in range(nvis):
                gwgt = wgt_raw[i, :] > 0
                ngwgt = wgt_raw[i, gwgt].size
                if ngwgt > 2:
                    reali = real_raw[i, gwgt]
                    imagi = imag_raw[i, gwgt]
                    rms_real = numpy.std(reali)
                    rms_imag = numpy.std(imagi)
                    rms_avg = (rms_real + rms_imag) / 2.
                    wgt_scaled[i, gwgt] = 1 / rms_avg ** 2
            wgt[:, :, ipol] = wgt_scaled
        visfile[0].data['DATA'][:, 0, 0, :, :, 2] = wgt

    # write out the uvfits data
    visfile.writeto(newvisdataloc)

def scalewt(visdataloc, newvisdataloc):

    visfile = fits.open(visdataloc)
    data_real, data_imag, data_wgt = visload(visfile)

    # scale the weights such that:
    # Sum(wgt * real^2 + wgt * imag^2) = N_visibilities
    wgt_scaled = data_wgt
    wgzero = wgt_scaled > 0
    N_vis = 2 * wgt_scaled[wgzero].size
    wgtrealimag = wgt_scaled * (data_real ** 2 + data_imag ** 2)
    wgtsum = wgtrealimag[wgzero].sum()
    wgtscale = N_vis / wgtsum
    print wgtscale
    wgt_scaled = wgt_scaled * wgtscale

    # read in the uvfits data
    if data_real.ndim == 4:
        visfile[0].data['DATA'][:, 0, 0, :, :, :, 2] = wgt_scaled
    else:
        visfile[0].data['DATA'][:, 0, 0, :, :, 2] = wgt_scaled
    visfile.writeto(newvisdataloc)

def zerowt(visdataloc, newvisdataloc, ExcludeChannels):

    visfile = fits.open(visdataloc)
    data_real, data_imag, data_wgt = visload(visfile)
    nwindows = len(ExcludeChannels) / 2
    for win in range(0, nwindows * 2, 2):
        chan1 = ExcludeChannels[win]
        chan2 = ExcludeChannels[win + 1]
        if data_real.ndim == 4:
            visfile[0].data['DATA'][:, 0, 0, :, chan1:chan2, :, 2] = 0.0
        else:
            visfile[0].data['DATA'][:, 0, 0, chan1:chan2, :, 2] = 0.0
    visfile.writeto(newvisdataloc)

# AS OF 2014-02-24, spectralavg IS NON-FUNCTIONAL
def spectralavg(visdataloc, newvisdataloc, Nchannels):
    # bin in frequency space to user's desired spectral resolution
    vis_data = fits.open(visdataloc)
    data_real, data_imag, data_wgt = visload(vis_data)

    # get the number of visibilities, spws, frequencies, polarizations
    if data_real.ndim == 4:
        nvis = data_real[:, 0, 0, 0].size
        nspw = data_real[0, :, 0, 0].size
        nchan = data_real[0, 0, :, 0].size
        npol = data_real[0, 0, 0, :].size
        real_bin = numpy.zeros([nvis, nspw, Nchannels, npol])
        imag_bin = numpy.zeros([nvis, nspw, Nchannels, npol])
        wgt_bin = numpy.zeros([nvis, nspw, Nchannels, npol])
    if data_real.ndim == 3:
        nvis = data_real[:, 0, 0].size
        nspw = 0
        nchan = data_real[0, :, 0].size
        npol = data_real[0, 0, :].size
        real_bin = numpy.zeros([nvis, Nchannels, npol])
        imag_bin = numpy.zeros([nvis, Nchannels, npol])
        wgt_bin = numpy.zeros([nvis, Nchannels, npol])

    chan1 = 0
    dchan = nchan / Nchannels
    chan2 = chan1 + dchan
    if nspw > 1:
        for ispw in range(nspw):

            for ipol in range(npol):

                for ichan in range(Nchannels):

                    for i in range(nvis):
                        gwgt = data_wgt[i, ispw, chan1:chan2, ipol] > 0
                        ngwgt = data_wgt[i, ispw, gwgt, ipol].size
                        if ngwgt == 0:
                            continue
                        value = data_real[i, ispw, gwgt, ipol].sum() / ngwgt
                        real_bin[i, ispw, ichan, ipol] = value
                        value = data_imag[i, ispw, gwgt, ipol].sum() / ngwgt
                        imag_bin[i, ispw, ichan, ipol] = value
                        value = data_wgt[i, ispw, gwgt, ipol].mean() * ngwgt
                        wgt_bin[i, ispw, ichan, ipol] = value
                    chan1 = chan2
                    chan2 = chan1 + dchan

        newvis = numpy.zeros([nvis, 1, 1, nspw, Nchannels, npol, 3])
        newvis[:, 0, 0, :, :, :, 0] = real_bin
        newvis[:, 0, 0, :, :, :, 1] = imag_bin
        newvis[:, 0, 0, :, :, :, 2] = wgt_bin

        oldcrpix4 = vis_data[0].header['CRPIX4']
        newcrpix4 = numpy.float(oldcrpix4) / nchan * Nchannels
        newcrpix4 = numpy.floor(newcrpix4) + 1
        vis_data[0].header['CRPIX4'] = newcrpix4

        oldcdelt4 = vis_data[0].header['CDELT4']
        newcdelt4 = oldcdelt4 * nchan / Nchannels
        vis_data[0].header['CDELT4'] = newcdelt4
    else:
        for ipol in range(npol):

            for ichan in range(Nchannels):

                for i in range(nvis):
                    gwgt = data_wgt[i, chan1:chan2, ipol] > 0
                    ngwgt = data_wgt[i, gwgt, ipol].size
                    if ngwgt == 0:
                        continue
                    value = data_real[i, gwgt, ipol].sum() / ngwgt
                    real_bin[i, ichan, ipol] = value
                    value = data_imag[i, gwgt, ipol].sum() / ngwgt
                    imag_bin[i, ichan, ipol] = value
                    value = data_wgt[i, gwgt, ipol].mean() * ngwgt
                    wgt_bin[i, ichan, ipol] = value
                chan1 = chan2
                chan2 = chan1 + dchan

        newvis = numpy.zeros([nvis, 1, 1, Nchannels, npol, 3])
        newvis[:, 0, 0, :, :, 0] = real_bin
        newvis[:, 0, 0, :, :, 1] = imag_bin
        newvis[:, 0, 0, :, :, 2] = wgt_bin

        oldcrpix4 = vis_data[0].header['CRPIX4']
        newcrpix4 = numpy.float(oldcrpix4) / nchan * Nchannels
        newcrpix4 = numpy.floor(newcrpix4) + 1
        vis_data[0].header['CRPIX4'] = newcrpix4
        vis_data[0].header['NAXIS4'] = Nchannels

        oldcdelt4 = vis_data[0].header['CDELT4']
        newcdelt4 = oldcdelt4 * nchan / Nchannels
        vis_data[0].header['CDELT4'] = newcdelt4
    vis_data[0].data['DATA'][:] = newvis
    vis_data.writeto(newvisdataloc)
