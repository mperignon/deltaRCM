from math import floor, sqrt
import numpy as np
from random import shuffle
from matplotlib import pyplot as plt
from scipy import ndimage
import sys, os
import pickle



class deltaRCM:

    #############################################
    ################### tools ###################
    #############################################

    def flatten_indices(self, ind):
        '''
        Flatten indices
        '''

        return ind[0]*self.W + ind[1]



    def random_pick(self, probs):
        '''
        Randomly pick a number weighted by array probs (len 8)

        Return the index of the selected weight in array probs
        '''

        if np.max(probs) == 0:
            probs = list([1/8 for i in range(8)])

        cutoffs = np.cumsum(probs)
        idx = cutoffs.searchsorted(np.random.uniform(0, cutoffs[-1]))

        return idx



    def random_pick_inlet(self, choices, probs = None):
        '''
        Randomly pick a number from array choices weighted by array probs
        Values in choices are column indices

        Return a tuple of the randomly picked index for row 0
        '''

        if not probs:
            probs = list([1 for i in range(len(choices))])

        cutoffs = np.cumsum(probs)
        idx = cutoffs.searchsorted(np.random.uniform(0, cutoffs[-1]))

        return (0,choices[idx])



    def neighbors(self, ind):
        '''
        Get indices of the 8 neighbor cells clockwise from the east
        '''

        i = ind[0]; j = ind[1]

        return [(i + self.dxn_iwalk[k], j + self.dxn_jwalk[k]) for k in range(8)]



    def save_figure(self, path, ext='png', close=True):
        '''
        Save a figure from pyplot.

        path : string
            The path (and filename without extension) to save the figure to.
        ext : string (default='png')
            The file extension. This must be supported by the active
            matplotlib backend (see matplotlib.backends module).  Most
            backends support 'png', 'pdf', 'ps', 'eps', and 'svg'.
        '''

        directory = os.path.split(path)[0]
        filename = "%s.%s" % (os.path.split(path)[1], ext)
        if directory == '': directory = '.'

        if not os.path.exists(directory):
            os.makedirs(directory)

        savepath = os.path.join(directory, filename)
        plt.savefig(savepath)

        if close: plt.close()



    def plot_data(self, timestep):

        if self.plot_figs and int(timestep+1) % self.plot_interval == 0:

            plt.pcolor(self.eta)
            plt.colorbar()
            if not self.save_figs:
                plt.show()
            if self.save_figs:
                self.save_figure("figs/" + self.fig_name_root + "eta" + str(timestep+1))

            plt.pcolor(self.stage)
            plt.colorbar()
            if not self.save_figs:
                plt.show()
            if self.save_figs:
                self.save_figure("figs/" + self.fig_name_root + "stage" + str(timestep+1))

            plt.pcolor(self.depth)
            plt.colorbar()
            if not self.save_figs:
                plt.show()
            if self.save_figs:
                self.save_figure("figs/" + self.fig_name_root + "depth" + str(timestep+1))



    #############################################
    ############### weight arrays ###############
    #############################################

    def build_weight_array(self, array, fix_edges = False, normalize = False):
        '''
        Create np.array((8,L,W)) of quantity a in each of the neighbors to a cell
        '''

        self.array = array
        a_shape = array.shape

        self.fix_edges = fix_edges
        self.normalize = normalize

        wgt_array = np.zeros((8,a_shape[0],a_shape[1]))
        nums = range(8)

        wgt_array[nums[0],:,:-1] = self.array[:,1:] # E
        wgt_array[nums[1],1:,:-1] = self.array[:-1,1:] # NE
        wgt_array[nums[2],1:,:] = self.array[:-1,:] # N
        wgt_array[nums[3],1:,1:] = self.array[:-1,:-1] # NW
        wgt_array[nums[4],:,1:] = self.array[:,:-1] # W
        wgt_array[nums[5],:-1,1:] = self.array[1:,:-1] # SW
        wgt_array[nums[6],:-1,:] = self.array[1:,:] # S
        wgt_array[nums[7],:-1,:-1] = self.array[1:,1:] # SE

        if self.fix_edges:
            wgt_array[nums[0],:,-1] = wgt_array[nums[0],:,-2]
            wgt_array[nums[1],:,-1] = wgt_array[nums[1],:,-2]
            wgt_array[nums[7],:,-1] = wgt_array[nums[7],:,-2]
            wgt_array[nums[1],0,:] = wgt_array[nums[1],1,:]
            wgt_array[nums[2],0,:] = wgt_array[nums[2],1,:]
            wgt_array[nums[3],0,:] = wgt_array[nums[3],1,:]
            wgt_array[nums[3],:,0] = wgt_array[nums[3],:,1]
            wgt_array[nums[4],:,0] = wgt_array[nums[4],:,1]
            wgt_array[nums[5],:,0] = wgt_array[nums[5],:,1]
            wgt_array[nums[5],-1,:] = wgt_array[nums[5],-2,:]
            wgt_array[nums[6],-1,:] = wgt_array[nums[6],-2,:]
            wgt_array[nums[7],-1,:] = wgt_array[nums[7],-2,:]

        if self.normalize:
            a_sum = np.sum(wgt_array, axis=0)
            wgt_array[:,a_sum!=0] = wgt_array[:,a_sum!=0] / a_sum[a_sum!=0]

        return wgt_array



    def get_wet_mask_nh(self):
        '''
        Get np.array((8,L,W)) for each neighbor around a cell
        with 1 if te neighbor is wet and 0 if dry
        '''

        wet_mask = (self.depth > self.dry_depth) * 1
        wet_mask_nh = self.build_weight_array(wet_mask, fix_edges = True)

        return wet_mask_nh



    def get_wgt_sfc(self, wet_mask_nh):
        '''
        Get np.array((8,L,W)) (H - H_neighbor)/dist
        for each neighbor around a cell

        Takes an narray of the same size with 1 if wet and 0 if not
        '''

        wgt_sfc = self.build_weight_array(self.stage, fix_edges = True)

        wgt_sfc = (self.stage - wgt_sfc) / np.array(self.dxn_dist)[:, np.newaxis, np.newaxis]

        wgt_sfc = wgt_sfc * wet_mask_nh
        wgt_sfc[wgt_sfc<0] = 0

        wgt_sfc_sum = np.sum(wgt_sfc,axis=0)
        wgt_sfc[:,wgt_sfc_sum>0] = wgt_sfc[:,wgt_sfc_sum>0] / wgt_sfc_sum[wgt_sfc_sum>0]

        return wgt_sfc



    def get_wgt_int(self, wet_mask_nh):
        '''
        Get np.array((8,L,W)) (qx*dxn_ivec + qy*dxn_jvec)/dist
        for each neighbor around a cell

        Takes an narray of the same size with 1 if wet and 0 if not
        '''

        wgt_int = (self.qx * np.array(self.dxn_ivec)[:,np.newaxis,np.newaxis] + \
            self.qy * np.array(self.dxn_jvec)[:,np.newaxis,np.newaxis]) / \
            np.array(self.dxn_dist)[:,np.newaxis,np.newaxis]

        wgt_int[1:4,0,:] = 0

        wgt_int = wgt_int * wet_mask_nh
        wgt_int[wgt_int<0] = 0
        wgt_int_sum = np.sum(wgt_int, axis=0)

        wgt_int[:,wgt_int_sum>0] = wgt_int[:,wgt_int_sum>0]/wgt_int_sum[wgt_int_sum>0]

        return wgt_int



    def get_wgt(self):
        '''
        Get np.array((8,L,W)) of the probabilities of flow
        between a cell and each of its neighbors

        If the probabilities are zero in all directions, they will
        be split equally among all wet neighbors
        '''

        wet_mask_nh = self.get_wet_mask_nh()
        wgt_sfc = self.get_wgt_sfc(wet_mask_nh)
        wgt_int = self.get_wgt_int(wet_mask_nh)


        weight = self.gamma * wgt_sfc + (1-self.gamma) * wgt_int

        wgt = self.build_weight_array(self.depth, fix_edges = True)
        wgt = wgt**self.theta_water * weight

        wet_mask = 1*(self.depth > self.dry_depth)
        wgt = wgt * wet_mask
        wgt[wgt<0] = 0
        wgt_sum = np.sum(wgt,axis=0)
        wgt[:,wgt_sum>0] = wgt[:,wgt_sum>0] / wgt_sum[wgt_sum>0]

        # give wet cells with zero wgt to all wet neighbors equal probs for each of them
        # wet cells with zero probabilities to all neighbors
        wet_mask = 1*(self.depth > self.dry_depth)

        wet_cells = np.where((wgt_sum + (wet_mask-1)) == 0)

        wet = [(wet_cells[0][i],wet_cells[1][i]) for i in range(len(wet_cells[0]))]

        # new weights to those cells - partitioned equally among the wet neighbors
        new_vals = [wet_mask_nh[:,i[0],i[1]]/sum(wet_mask_nh[:,i[0],i[1]]) for i in wet]

        for i in range(len(new_vals)):
            wgt[:,wet[i][0],wet[i][1]] = new_vals[i]

        wgt[1:4,0,:] = 0

        return wgt



    def get_sed_weight(self):
        '''
        Get np.array((8,L,W)) of probability field of routing to neighbors
        for sediment parcels
        '''

        wet_mask_nh = self.get_wet_mask_nh()

        weight = self.get_wgt_int(wet_mask_nh) * \
            self.depth**self.theta_sand * wet_mask_nh

        weight[weight<0] = 0.
        weight_sum = np.sum(weight,axis=0)
        weight[:,weight_sum>0] = weight[:,weight_sum>0]/weight_sum[weight_sum>0]

        weight_f = np.zeros((self.L*self.W,8))

        for i in range(8):
            weight_f[:,i] = weight[i,:,:].flatten()

        return weight_f



    #############################################
    ################# smoothing #################
    #############################################

    def smoothing_filter(self, stageTemp):
        '''
        Smooth water surface

        If any of the cells in a 9-cell window are wet, apply this filter

        stageTemp : water surface
        stageT : smoothed water surface
        '''

        stageT = stageTemp.copy()
        wet_mask = self.depth > self.dry_depth

        for t in range(self.Nsmooth):

            local_mean = ndimage.uniform_filter(stageT)

            stageT[wet_mask] = self.Csmooth * stageT[wet_mask] + \
                (1-self.Csmooth) * local_mean[wet_mask]

        returnval = (1-self.omega_sfc) * self.stage + self.omega_sfc * stageT

        return returnval



    def flooding_correction(self):
        '''
        Flood dry cells along the shore if necessary

        Check the neighbors of all dry cells. If any dry cells have wet neighbors
        Check that their stage is not higher than the bed elevation of the center cell
        If it is, flood the dry cell
        '''

        wet_mask = self.depth > self.dry_depth
        wet_mask_nh = self.get_wet_mask_nh()
        wet_mask_nh_sum = np.sum(wet_mask_nh, axis=0)

        # makes wet cells look like they have only dry neighbors
        wet_mask_nh_sum[wet_mask] = 0

        # indices of dry cells with wet neighbors
        shore_ind = np.where(wet_mask_nh_sum > 0)

        stage_nhs = self.build_weight_array(self.stage)
        eta_shore = self.eta[shore_ind]

        for i in range(len(shore_ind[0])):

            # pretends dry neighbor cells have stage zero so they cannot be > eta_shore[i]
            stage_nh = wet_mask_nh[:,shore_ind[0][i],shore_ind[1][i]] * \
                stage_nhs[:,shore_ind[0][i],shore_ind[1][i]]

            if (stage_nh > eta_shore[i]).any():
                self.stage[shore_ind[0][i],shore_ind[1][i]] = max(stage_nh)



    def topo_diffusion(self):
        '''
        Diffuse topography after routing all coarse sediment parcels
        '''

        wgt_cell_type = self.build_weight_array(self.cell_type > -2)
        wgt_qs = self.build_weight_array(self.qs) + self.qs
        wet_mask_nh = self.get_wet_mask_nh()

        multiplier = self.dt/self.N_crossdiff * self.alpha * 0.5 / self.dx**2

        for n in range(self.N_crossdiff):

            wgt_eta = self.build_weight_array(self.eta) - self.eta

            crossflux_nb = multiplier * wgt_qs * wgt_eta

            crossflux_nb = crossflux_nb * wet_mask_nh

            crossflux = np.sum(crossflux_nb, axis=0)
            self.eta = self.eta + crossflux



    #############################################
    ################# updaters ##################
    #############################################

    def update_flow_field(self, timestep, iteration):
        '''
        Update water discharge after one water iteration
        '''

        dloc = (self.qxn**2 + self.qyn**2)**(0.5)
        qwn_div = np.ones_like(self.qwn)
        qwn_div[dloc>0] = self.qwn[dloc>0] / dloc[dloc>0]
        self.qxn *= qwn_div
        self.qyn *= qwn_div

        if timestep > 0:

            omega = self.omega_flow_iter
            if iteration == 0: omega = self.omega_flow

            self.qx = self.qxn*omega + self.qx*(1-omega)
            self.qy = self.qyn*omega + self.qy*(1-omega)

        else:

            self.qx = self.qxn.copy(); self.qy = self.qyn.copy()

        self.qw = (self.qx**2 + self.qy**2)**(0.5)
        self.qx[0,self.inlet] = self.qw0
        self.qy[0,self.inlet] = 0
        self.qw[0,self.inlet] = self.qw0



    def update_velocity_field(self):
        '''
        Update the flow velocity field after one water iteration
        '''

        mask = (self.depth > self.dry_depth) * (self.qw > 0)
        self.uw[mask] = np.minimum(self.u_max, self.qw[mask] / self.depth[mask])
        self.uw[~mask] = 0
        self.ux[mask]= self.uw[mask] * self.qx[mask] / self.qw[mask]
        self.ux[~mask] = 0
        self.uy[mask]= self.uw[mask] * self.qy[mask] / self.qw[mask]
        self.uy[~mask] = 0



    #############################################
    ################# water flow ################
    #############################################

    def init_water_iteration(self):

        wgt = self.get_wgt()

        for i in range(8):
            self.wgt_flat[:,i] = wgt[i,:,:].flatten()

        self.qxn[:] = 0; self.qyn[:] = 0; self.qwn[:] = 0

        self.indices = np.zeros((self.Np_water, self.itmax/2), dtype = np.int)
        self.path_number = np.array(range(self.Np_water))
        self.save_paths = []



    def run_water_iteration(self):
        '''
        Route all parcels of water in one iteration
        '''

        these_indices = map(lambda x: self.random_pick_inlet(self.inlet), range(self.Np_water))
        these_indices = map(self.flatten_indices, these_indices)

        self.indices[:,0] = these_indices
        self.qxn.flat[these_indices] += 1

        water_continue = True
        it = 0

        while water_continue:

            ngh = map(self.random_pick, self.wgt_flat[these_indices])
            new_indices = these_indices + self.walk_flat[ngh]
            new_ind_type = self.cell_type.flat[new_indices]

            # save the path numbers of the ones that reached the edge
            if self.path_number[new_ind_type == -1].any():
                self.save_paths.append( list(self.path_number[new_ind_type == -1]) )

            walk_vals = self.walk[ngh]
            self.qxn.flat[these_indices] += walk_vals[:,0]
            self.qyn.flat[these_indices] += walk_vals[:,1]

            walk_vals = self.walk[list( np.array(ngh)[new_ind_type >= -1] )]
            n_these_indices = new_indices[new_ind_type >= -1]
            n_path_number = self.path_number[new_ind_type >= -1]
            for i in range(len(n_these_indices)):
                self.qxn.flat[n_these_indices[i]] += walk_vals[i,0]
                self.qyn.flat[n_these_indices[i]] += walk_vals[i,1]

            it += 1
            self.indices[n_path_number,it] = n_these_indices

            these_indices = new_indices[new_ind_type >= 0]
            self.path_number = self.path_number[new_ind_type >= 0]

            # check for looping
            if len(self.path_number)>0:
                keeper = np.ones((len(these_indices),), dtype=np.int)
                for i in range(len(these_indices)):

                    if np.in1d(self.indices[self.path_number[i],:it], these_indices[i]).any():
                        keeper[i] = 0

                    if these_indices[i]<0:
                        keeper[i] = 0

                if np.min(keeper)==0:

                    these_indices = these_indices[keeper == 1]
                    self.path_number = self.path_number[keeper == 1]

            if it == self.itmax-1 or len(these_indices)==0:
                water_continue = False

        # update qwn by counting the indices
        all_indices = self.indices.flatten()
        all_indices.sort()
        loc = np.where(all_indices>0)[0][0]
        ind_index_all = all_indices[loc:]

        ind_count = np.bincount(ind_index_all)
        ind_index = range(max(ind_index_all)+1)

        qwn_sum = ind_count[ind_index] * self.Qp_water/self.dx

        self.qwn.flat[ind_index] += qwn_sum



    def finalize_water_iteration(self, timestep, iteration):
        '''
        Finish updating flow fields
        Clean up at end of water iteration
        '''

        self.flooding_correction()
        self.stage = np.maximum(self.stage, self.H_SL)
        self.depth = np.maximum(self.stage - self.eta, 0)

        self.update_flow_field(timestep, iteration)
        self.update_velocity_field()



    def get_profiles(self):
        '''
        Calculate the water surface profiles after routing flow parcels
        Update water surface array
        '''

        paths_for_profile = [i for j in self.save_paths for i in j]

        assert len(paths_for_profile) == len(set(paths_for_profile)), "save_paths has repeats!"

        # get all the unique indices in good paths
        unique_cells = list(set([j for i in paths_for_profile for j in list(set(self.indices[i]))]))
        try:
            unique_cells.remove(0)
        except:
            pass

        unique_cells.sort()

        # extract the values needed for the paths -- no need to do this for the entire space
        uw_unique = self.uw.flat[unique_cells]
        depth_unique = self.depth.flat[unique_cells]
        ux_unique = self.ux.flat[unique_cells]
        uy_unique = self.uy.flat[unique_cells]

        profile_mask = np.add(uw_unique > 0.5*self.u0, depth_unique < 0.1*self.h0)

        all_unique = zip(profile_mask,uw_unique,ux_unique,uy_unique)

        sfc_array = np.zeros((len(unique_cells),2))

        # make dictionaries to use as lookup tables
        lookup = {}
        self.sfc_change = {}

        for i in range(len(unique_cells)):
            lookup[unique_cells[i]] = all_unique[i]
            self.sfc_change[unique_cells[i]] = sfc_array[i]

        # process each profile
        for i in paths_for_profile:

            path = self.indices[i]
            path = path[np.where(path>0)]

            prf = [lookup[i][0] for i in path]

            # find the last True
            try:
                last_True = (len(prf) - 1) - prf[::-1].index(True)
                sub_path = path[:last_True]

                sub_path_unravel = np.unravel_index(sub_path, self.eta.shape)

                path_diff = np.diff(sub_path_unravel)
                ux_ = [lookup[i][2] for i in sub_path[:-1]]
                uy_ = [lookup[i][3] for i in sub_path[:-1]]
                uw_ = [lookup[i][1] for i in sub_path[:-1]]

                dH = self.S0 * (ux_ * path_diff[0] + uy_ * path_diff[1]) * self.dx
                dH = [dH[i] / uw_[i] if uw_[i]>0 else 0 for i in range(len(dH))]
                dH.append(0)

                newH = np.zeros(len(sub_path))
                for i in range(-2,-len(sub_path)-1,-1):
                    newH[i] = newH[i+1] + dH[i]

                for i in range(len(sub_path)):
                    self.sfc_change[sub_path[i]] += [newH[i],1]
            except:
                pass

        stageTemp = self.eta + self.depth

        for k, v in self.sfc_change.iteritems():
            if np.max(v) > 0:
                stageTemp.flat[k] = v[0]/v[1]

        self.stage = self.smoothing_filter(stageTemp)



    #############################################
    ################# sed flow ##################
    #############################################

    def init_sed_timestep(self):
        '''
        Set up arrays to start sed routing timestep
        '''

        self.qs[:] = 0
        self.Vp_dep_sand[:] = 0
        self.Vp_dep_mud[:] = 0



    def one_fine_timestep(self):
        '''
        Route all parcels of fine sediment
        '''

        self.num_fine = int(self.Np_sed - self.num_coarse)

        if self.num_fine>0:

            these_indices = map(lambda x: self.random_pick_inlet(self.inlet),range(self.num_fine))
            these_indices = map(self.flatten_indices,these_indices)

            self.indices = np.zeros((self.num_fine,self.itmax), dtype=np.int)
            self.indices[:,0] = these_indices

            path_number = np.array(range(self.num_fine))
            self.Vp_res = np.zeros((self.Np_sed,)) + self.Vp_sed
            self.qs.flat[these_indices] += self.Vp_res[path_number]/2/self.dt/self.dx

            sed_continue = True
            it = 0

            while sed_continue:

                weight = self.get_sed_weight()

                ngh = map(self.random_pick, weight[these_indices])
                new_indices = these_indices + self.walk_flat[ngh]
                new_ind_type = self.cell_type.flat[new_indices]

                self.qs.flat[these_indices] += self.Vp_res[path_number]/2/self.dt/self.dx
                self.qs.flat[new_indices] += self.Vp_res[path_number]/2/self.dt/self.dx


                these_indices = new_indices[new_ind_type >= 0]
                path_number = path_number[new_ind_type >= 0]

                if len(path_number)>0:
                    # check for looping
                    keeper = np.ones((len(these_indices),), dtype=np.int)
                    for i in range(len(these_indices)):
                        if np.in1d(self.indices[path_number[i],:], these_indices[i]).any():
                            keeper[i] = 0
                        if these_indices[i]<0:
                            keeper[i] = 0
                    if np.min(keeper)==0:
                        these_indices = these_indices[keeper == 1]
                        path_number = path_number[keeper == 1]

                # save to the master indices
                it += 1
                self.indices[path_number,it] = these_indices


                if (self.uw.flat[these_indices] < self.U_dep_mud).any():

                    update_ind = these_indices[self.uw.flat[these_indices] < self.U_dep_mud]
                    update_path = path_number[self.uw.flat[these_indices] < self.U_dep_mud]
                    Vp_res_ = self.Vp_res[update_path]

                    Vp_res_ = self.sed_lag * Vp_res_ * (self.U_dep_mud**self.beta - self.uw.flat[update_ind]**self.beta) / (self.U_dep_mud**self.beta)

                    self.Vp_dep = (self.stage.flat[update_ind] - self.eta.flat[update_ind])/4 * self.dx**2
                    self.Vp_dep = np.array([min((Vp_res_[i],self.Vp_dep[i])) for i in range(len(self.Vp_dep))])
                    self.Vp_dep_mud.flat[update_ind] += self.Vp_dep

                    self.Vp_res[update_path] -= self.Vp_dep

                    self.eta.flat[update_ind] += self.Vp_dep / self.dx**2
                    self.depth.flat[update_ind] = self.stage.flat[update_ind] - self.eta.flat[update_ind]
                    update_uw = [min(self.u_max, self.qw.flat[i]/self.depth.flat[i]) for i in update_ind]
                    self.uw.flat[update_ind] = update_uw

                    update_uwqw = [self.uw.flat[i]/self.qw.flat[i] if self.qw.flat[i]>0 else 0 for i in update_ind]
                    self.ux.flat[update_ind] = self.qx.flat[update_ind] * update_uwqw
                    self.uy.flat[update_ind] = self.qy.flat[update_ind] * update_uwqw


                if (self.uw.flat[these_indices] > self.U_ero_mud).any():

                    update_ind = these_indices[self.uw.flat[these_indices] > self.U_ero_mud]
                    update_path = path_number[self.uw.flat[these_indices] > self.U_ero_mud]

                    Vp_res_ = self.Vp_sed * (self.uw.flat[update_ind]**self.beta - self.U_ero_mud**self.beta) / (self.U_ero_mud**self.beta)
                    self.Vp_ero = (self.stage.flat[update_ind] - self.eta.flat[update_ind])/4 * self.dx**2
                    self.Vp_ero = np.array([min((Vp_res_[i],self.Vp_ero[i])) for i in range(len(self.Vp_ero))])

                    self.eta.flat[update_ind] -= self.Vp_ero / self.dx**2

                    self.depth.flat[update_ind] = self.stage.flat[update_ind] - self.eta.flat[update_ind]
                    update_uw = [min(self.u_max, self.qw.flat[i]/self.depth.flat[i]) for i in update_ind]
                    self.uw.flat[update_ind] = update_uw

                    update_uwqw = [self.uw.flat[i]/self.qw.flat[i] if self.qw.flat[i]>0 else 0 for i in update_ind]
                    self.ux.flat[update_ind] = self.qx.flat[update_ind] * update_uwqw
                    self.uy.flat[update_ind] = self.qy.flat[update_ind] * update_uwqw

                    self.Vp_res[update_path] += self.Vp_ero


                if it == self.itmax-1 or len(these_indices)==0:
                    sed_continue = False



    def one_coarse_timestep(self):
        '''
        Route all parcels of coarse sediment
        '''

        self.num_coarse = int(round(self.Np_sed*self.f_bedload))

        if self.num_coarse>0:

            these_indices = map(lambda x: self.random_pick_inlet(self.inlet),range(self.num_coarse))
            these_indices = map(self.flatten_indices,these_indices)

            self.indices = np.zeros((self.num_coarse,self.itmax), dtype=np.int)
            self.indices[:,0] = these_indices

            path_number = np.array(range(self.num_coarse))
            self.Vp_res = np.zeros((self.Np_sed,)) + self.Vp_sed
            self.qs.flat[these_indices] += self.Vp_res[path_number]/2/self.dt/self.dx

            sed_continue = True
            it = 0

            while sed_continue:

                weight = self.get_sed_weight()

                ngh = map(self.random_pick, weight[these_indices])
                new_indices = these_indices + self.walk_flat[ngh]
                new_ind_type = self.cell_type.flat[new_indices]

                self.qs.flat[these_indices] += self.Vp_res[path_number]/2/self.dt/self.dx
                self.qs.flat[new_indices] += self.Vp_res[path_number]/2/self.dt/self.dx

                these_indices = new_indices[new_ind_type >= 0]
                path_number = path_number[new_ind_type >= 0]

                if len(path_number)>0:
                    # check for looping
                    keeper = np.ones((len(these_indices),), dtype=np.int)
                    for i in range(len(these_indices)):
                        if np.in1d(self.indices[path_number[i],:], these_indices[i]).any():
                            keeper[i] = 0
                        if these_indices[i]<0:
                            keeper[i] = 0
                    if np.min(keeper)==0:
                        these_indices = these_indices[keeper == 1]
                        path_number = path_number[keeper == 1]

                it += 1
                self.indices[path_number,it] = these_indices

                qs_cap = self.qs0 * self.f_bedload/self.u0**self.beta * self.uw.flat[these_indices]**self.beta


                if (self.qs.flat[these_indices] > qs_cap).any():

                    update_ind = these_indices[self.qs.flat[these_indices] > qs_cap]
                    update_path = path_number[self.qs.flat[these_indices] > qs_cap]
                    Vp_res_ = self.Vp_res[update_path]

                    self.Vp_dep = (self.stage.flat[update_ind] - self.eta.flat[update_ind])/4 * self.dx**2
                    self.Vp_dep = np.array([min((Vp_res_[i],self.Vp_dep[i])) for i in range(len(update_ind))])
                    eta_change = self.Vp_dep / self.dx**2
                    self.Vp_res[update_path] -= self.Vp_dep
                    self.Vp_dep_sand.flat[update_ind] += self.Vp_dep

                    self.eta.flat[update_ind] += eta_change

                    update_uw = [min(self.u_max, self.qw.flat[i]/self.depth.flat[i]) for i in update_ind]
                    self.uw.flat[update_ind] = update_uw

                    update_uwqw = [self.uw.flat[i]/self.qw.flat[i] if self.qw.flat[i]>0 else 0 for i in update_ind]
                    self.ux.flat[update_ind] = self.qx.flat[update_ind] * update_uwqw
                    self.uy.flat[update_ind] = self.qy.flat[update_ind] * update_uwqw


                if ((self.qs.flat[these_indices] < qs_cap) * (self.uw.flat[these_indices] > self.U_ero_sand)).any():

                    update_ind = these_indices[(self.qs.flat[these_indices] < qs_cap) * (self.uw.flat[these_indices] > self.U_ero_sand)]
                    update_path = path_number[(self.qs.flat[these_indices] < qs_cap) * (self.uw.flat[these_indices] > self.U_ero_sand)]

                    Vp_res_ = self.Vp_sed * (self.uw.flat[update_ind]**self.beta - self.U_ero_sand**self.beta) / (self.U_ero_sand**self.beta)
                    Vp_ero_ = (self.stage.flat[update_ind] - self.eta.flat[update_ind])/4 * self.dx**2
                    self.Vp_ero = np.array([min((Vp_res_[i],Vp_ero_[i])) for i in range(len(update_ind))])

                    self.eta.flat[update_ind] -= self.Vp_ero / self.dx**2
                    self.depth.flat[update_ind] = self.stage.flat[update_ind] - self.eta.flat[update_ind]


                    update_uw = [min(self.u_max, self.qw.flat[i]/self.depth.flat[i]) for i in update_ind]
                    self.uw.flat[update_ind] = update_uw

                    update_uwqw = [self.uw.flat[i]/self.qw.flat[i] if self.qw.flat[i]>0 else 0 for i in update_ind]
                    self.ux.flat[update_ind] = self.qx.flat[update_ind] * update_uwqw
                    self.uy.flat[update_ind] = self.qy.flat[update_ind] * update_uwqw

                    self.Vp_res[update_path] += self.Vp_ero


                if it == self.itmax-1 or len(these_indices)==0:
                    sed_continue = False

        self.topo_diffusion()



    def finalize_sed_timestep(self):
        '''
        Clean up after sediment routing
        Update sea level if baselevel changes
        '''

        self.flooding_correction()
        self.stage = np.maximum(self.stage, self.H_SL)
        self.depth = np.maximum(self.stage-self.eta, 0)

        self.eta[0,self.inlet] = self.stage[0,self.inlet] - self.h0
        self.depth[0,self.inlet] = self.h0

        self.H_SL = self.H_SL + self.SLR * self.dt



    #############################################
    ############## initialization ###############
    #############################################

    def initialize_variables(self):
        '''
        Set the seldom used variables (called by __init__)
        '''

        self.L = int(round(self.Length/self.dx))        # num cells in x
        self.W = int(round(self.Width/self.dx))         # num cells in y

        self.u0 = 1.                        # characteristic flow velocity
                                            # (also inlet channel velocity)

        self.u_max = 2.0 * self.u0          # maximum allowed flow velocity
        
        self.h0 = 5.                # characteristic flow depth
                                    # (also inlet flow depth)
        self.N0 = 5                 # num cells across inlet
        self.L0 = 3                 # width of landmass

        # characteristic topographic slope
        self.S0 = 0.0003 * self.f_bedload + 0.0001 * (1 - self.f_bedload)

        self.H_SL = 0.          # sea-level elevation (ds boundary condition)
        self.SLR = 0.           # sea-level rise per time step

        # (m) critial depth to switch to "dry" node
        self.dry_depth = min(0.1, 0.1*self.h0)
        self.CTR = floor(self.W/2)

        self.g = 9.81
        self.gamma = self.g * self.S0 * self.dx / (self.u0**2)

        self.V0 = self.h0 * (self.dx**2)    # (m^3) reference volume (volume to
                                            # fill cell to characteristic depth)

        self.Qw0 = self.u0 * self.h0 * self.N0 * self.dx    # const discharge
                                                            # at inlet
                                                            
        self.qw0 = self.u0 * self.h0                # water unit input discharge
        self.Qp_water = self.Qw0 / self.Np_water    # volume each water parcel

        self.C0 = 0.1 * 1/100                       # sediment concentration
        self.qs0 = self.qw0 * self.C0               # sed unit discharge

        self.dVs = 0.1 * self.N0**2 * self.V0       # total amount of sed added 
                                                    # to domain per timestep

        self.Qs0 = self.Qw0 * self.C0           # sediment total input discharge
        self.Vp_sed = self.dVs / self.Np_sed    # volume of each sediment parcel
        self.U_dep_mud = 0.3 * self.u0
        self.U_ero_sand = 1.05 * self.u0
        self.U_ero_mud = 1.5 * self.u0

        self.itmax = 2 * (self.L + self.W)      # max number of jumps for parcel
        self.dt = self.dVs / self.Qs0           # time step size

        # depth depedence (power of h) in routing X parcels
        self.theta_water = 1.0                              # water parcels
        self.theta_sand = 2.0 * self.theta_water            # sand parcels
        self.theta_mud = 1.0 * self.theta_water             # mud parcels

        self.beta = 3           # non-linear exponent of sediment flux
                                # to flow velocity
        self.sed_lag = 1.0      # "sedimentation lag" - 1.0 == no lag
                                # lambda in Matlab

        self.Csmooth = 0.9          # center-weighted surface smoothing
        self.omega_sfc = 0.1        # under-relaxation coeff for water surface
        self.Nsmooth = 5            # number of times to run smoothing algorithm
        self.omega_flow = 0.9
        self.omega_flow_iter = 2 / self.itermax

        self.alpha = 0.1                # topo diffusion coefficient
        
        # number of times to repeat topo diffusion
        self.N_crossdiff = int(round(self.dVs / self.V0))



    def create_domain(self):
        '''
        Creates the model domain
        '''

        x, y = np.meshgrid(np.arange(0,self.W), np.arange(0,self.L))

        cell_type = np.zeros_like(x)                                # ocean
        cell_type[((y-3)**2 + (x-self.CTR)**2)**(0.5) > self.L-5] = -1     # out
        cell_type[:self.L0,:] = 2                                   # land
        channel_inds = int(self.CTR-round(self.N0/2))
        cell_type[:self.L0,channel_inds:channel_inds+self.N0] = 1   # channel

        self.inlet = list(np.unique(np.where(cell_type == 1)[1]))

        eta = np.zeros_like(x).astype(np.float32, copy=False)
        stage = np.zeros_like(eta)
        depth = np.zeros_like(eta)

        stage = (self.L0-y-1) * self.dx * self.S0
        stage[cell_type <= 0] = 0.
        depth[cell_type <= 0] = self.h0
        depth[cell_type == 1] = self.h0

        # initialize flow conditions
        self.qx = np.zeros_like(eta)
        self.qy = np.zeros_like(eta)
        self.qxn = np.zeros_like(eta)
        self.qyn = np.zeros_like(eta)
        self.qwn = np.zeros_like(eta)
        self.ux = np.zeros_like(eta)
        self.uy = np.zeros_like(eta)
        self.uw = np.zeros_like(eta)

        self.qx[cell_type == 1] = self.qw0
        self.qx[cell_type <= 0] = self.qw0 / 5.
        self.qw = (self.qx**2 + self.qy**2)**(0.5)

        self.ux[depth>0] = self.qx[depth>0] / depth[depth>0]
        self.uy[depth>0] = self.qy[depth>0] / depth[depth>0]
        self.uw[depth>0] = self.qw[depth>0] / depth[depth>0]

        cell_type[cell_type == 2] = -2          # set the land cell_type to -2
        self.cell_type = cell_type
        self.eta = stage - depth
        self.depth = depth
        self.stage = stage

        self.dxn_iwalk = [1,1,0,-1,-1,-1,0,1]
        self.dxn_jwalk = [0,1,1,1,0,-1,-1,-1]
        self.dxn_dist = \
        [sqrt(self.dxn_iwalk[i]**2 + self.dxn_jwalk[i]**2) for i in range(8)]
        
        SQ05 = sqrt(0.5)
        self.dxn_ivec = [0,-SQ05,-1,-SQ05,0,SQ05,1,SQ05]
        self.dxn_jvec = [1,SQ05,0,-SQ05,-1,-SQ05,0,SQ05]

        self.walk_flat = np.array([1, -49, -50, -51, -1, 49, 50, 51])
        self.walk = np.array([[0,1], [-SQ05, SQ05], [-1,0], [-SQ05,-SQ05], 
                              [0,-1], [SQ05,-SQ05], [1,0], [SQ05,SQ05]])
        self.wgt_flat = np.zeros((self.L*self.W,8))

        self.qs, self.Vp_dep_sand, self.Vp_dep_mud = \
                        (np.zeros_like(self.eta) for _ in xrange(3))



    #############################################
    ############# run_one_timestep ##############
    #############################################

    def run_one_timestep(self, timestep):
        '''
        Run the time loop once
        '''

        if self.verbose: print '-'*20
        print 'Time = ' + str(timestep) + ' of ' + str(self.max_time)


        for iteration in range(self.itermax):

            self.init_water_iteration()
            self.run_water_iteration()

            if timestep>0:
                self.get_profiles()

            self.finalize_water_iteration(timestep, iteration)

        self.init_sed_timestep()

        self.one_coarse_timestep()
        self.one_fine_timestep()

        self.finalize_sed_timestep()



    #############################################
    ################### update ##################
    #############################################

    def update(self):
        '''
        Run the model for one full instance
        '''

        for timestep in range(self.max_time):
            self.run_one_timestep(timestep)
            self.plot_data(timestep)



    #############################################
    ################## __init__ #################
    #############################################

    def __init__(self):
        '''
        Creates an instance of the model

        Sets the most commonly changed variables here
        Calls functions to set the rest and create the domain (for cleanliness)
        '''

        self.Length = 200    # meters
        self.Width = 500     # meters
        self.dx = 10         # meters

        self.verbose = False
        self.plot_figs = True
        self.save_figs = True
        self.plot_interval = 10

        self.fig_name_root = ''

        self.max_time = 200
        self.itermax = 3
        self.Np_water = 200            # total number of water parcels
        self.Np_sed = 500            # total number of water parcels
        self.f_bedload = 0.25         # fraction of sediment that is bedload

        self.initialize_variables()
        self.create_domain()




delta = deltaRCM()
delta.update()


