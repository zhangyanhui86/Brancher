import matplotlib.pyplot as plt
import numpy as np
import seaborn as sbn
import pandas as pd

from brancher.variables import RootVariable, RandomVariable, ProbabilisticModel
from brancher.standard_variables import NormalVariable, LogNormalVariable, BetaVariable, MultivariateNormalVariable
from brancher import inference
import brancher.functions as BF

# N repetitions
N_rep = 15 #10

# Data list
condition_list = [lambda t: (t < 0 or t > 30), lambda t: True, lambda t: (t < 10 or t > 30)]
condition_label = ["Past", "Full", "Bridge"]

N_itr = 400
N_smpl = 20
optimizer = "SGD"
lr = 0.0001 #0.0002
N_ELBO_smpl = 1000


for cond, label in zip(condition_list, condition_label):
    ELBO1 = []
    ELBO2 = []
    ELBO3 = []
    ELBO4 = []
    for rep in range(N_rep):
        print("Repetition: {}".format(rep))
        # Probabilistic model #
        T = 40
        dt = 0.01
        driving_noise = 0.1
        measure_noise = 0.15
        x0 = NormalVariable(0., driving_noise, 'x0')
        y0 = NormalVariable(x0, measure_noise, 'y0')

        x = [x0]
        y = [y0]
        x_names = ["x0"]
        y_names = ["y0"]
        y_range = [t for t in range(T) if cond(t)]
        for t in range(1, T):
            x_names.append("x{}".format(t))
            x.append(NormalVariable(x[t - 1], np.sqrt(dt) * driving_noise, x_names[t]))
            if t in y_range:
                y_name = "y{}".format(t)
                y_names.append(y_name)
                y.append(NormalVariable(x[t], measure_noise, y_name))
        AR_model = ProbabilisticModel(x + y)

        # Generate data #
        data = AR_model._get_sample(number_samples=1)
        time_series = [float(data[yt].data) for yt in y]
        ground_truth = [float(data[xt].data) for xt in x]
        #true_b = data[omega].data
        #print("The true coefficient is: {}".format(float(true_b)))

        # Observe data #
        [yt.observe(data[yt][:, 0, :]) for yt in y]

        # Structured variational distribution #
        Qx = [NormalVariable(0., 1., 'x0', learnable=True)]
        Qx_mean = [RootVariable(0., 'x0_mean', learnable=True)]
        Qlambda = [RootVariable(-1., 'x0_lambda', learnable=True)]

        for t in range(1, T):
            if t in y_range:
                l = 0.
            else:
                l = 1.
            Qx_mean.append(RootVariable(0, x_names[t] + "_mean", learnable=True))
            Qlambda.append(RootVariable(l, x_names[t] + "_lambda", learnable=True))
            Qx.append(NormalVariable(BF.sigmoid(Qlambda[t]) * Qx[t - 1] + (1 - BF.sigmoid(Qlambda[t])) * Qx_mean[t],
                                     np.sqrt(dt) * driving_noise, x_names[t], learnable=True))
        variational_posterior = ProbabilisticModel(Qx)
        AR_model.set_posterior_model(variational_posterior)

        # Inference #
        inference.perform_inference(AR_model,
                                    number_iterations=N_itr,
                                    number_samples=N_smpl,
                                    optimizer=optimizer,
                                    lr=lr)

        loss_list1 = AR_model.diagnostics["loss curve"]

        # ELBO
        ELBO1.append(float(AR_model.estimate_log_model_evidence(N_ELBO_smpl).detach().numpy()))
        print("PE {}".format(ELBO1[-1]))

        # Mean-field variational distribution #
        Qx = [NormalVariable(0., 1., 'x0', learnable=True)]

        for t in range(1, T):
            Qx.append(NormalVariable(0, 2., x_names[t], learnable=True))
        variational_posterior = ProbabilisticModel(Qx)
        AR_model.set_posterior_model(variational_posterior)

        # Inference #
        inference.perform_inference(AR_model,
                                    number_iterations=N_itr,
                                    number_samples=N_smpl,
                                    optimizer=optimizer,
                                    lr=lr)

        loss_list2 = AR_model.diagnostics["loss curve"]

        # ELBO
        ELBO2.append(float(AR_model.estimate_log_model_evidence(N_ELBO_smpl).detach().numpy()))
        print("MF {}".format(ELBO2[-1]))

        # Multivariate normal variational distribution #

        QV = MultivariateNormalVariable(loc=np.zeros((T,)),
                                        scale_tril=np.identity(T),
                                        learnable=True)
        Qx = [NormalVariable(QV[0], 0.1, 'x0', learnable=True)]

        for t in range(1, T):
            Qx.append(NormalVariable(QV[t], 0.1, x_names[t], learnable=True))
        variational_posterior = ProbabilisticModel(Qx)
        AR_model.set_posterior_model(variational_posterior)

        # Inference #
        inference.perform_inference(AR_model,
                                    number_iterations=N_itr,
                                    number_samples=N_smpl,
                                    optimizer=optimizer,
                                    lr=lr)

        loss_list3 = AR_model.diagnostics["loss curve"]

        # ELBO
        ELBO3.append(float(AR_model.estimate_log_model_evidence(N_ELBO_smpl).detach().numpy()))
        print("MN {}".format(ELBO3[-1]))

        # Structured NN distribution #
        hidden_size = 10
        latent_size = 10
        Qepsilon = NormalVariable(np.zeros((10,1)), np.ones((10,)), 'epsilon', learnable=True)
        W1 = RootVariable(np.random.normal(0, 0.1, (hidden_size, latent_size)), "W1", learnable=True)
        W2 = RootVariable(np.random.normal(0, 0.1, (T, hidden_size)), "W2", learnable=True)
        pre_x = BF.matmul(W2, BF.sigmoid(BF.matmul(W1, Qepsilon)))
        Qx = []
        for t in range(0, T):
            Qx.append(NormalVariable(pre_x[t], 1., x_names[t], learnable=True))
        variational_posterior = ProbabilisticModel(Qx)
        AR_model.set_posterior_model(variational_posterior)

        # Inference #
        inference.perform_inference(AR_model,
                                    number_iterations=N_itr,
                                    number_samples=N_smpl,
                                    optimizer=optimizer,
                                    lr=lr)

        loss_list4 = AR_model.diagnostics["loss curve"]

        # ELBO
        ELBO4.append(float(AR_model.estimate_log_model_evidence(N_ELBO_smpl).detach().numpy()))
        print("NN {}".format(ELBO4[-1]))

        # plt.plot(loss_list1)
        # plt.plot(loss_list2)
        # plt.plot(loss_list3)
        # plt.plot(loss_list4)
        # plt.show()

    d = {'PE': ELBO1, 'MF': ELBO2, "MN": ELBO3, "NN": ELBO4}

    import pickle
    with open('{}_brownian_results.pickle'.format(label), 'wb') as f:
        pickle.dump(d, f)

    df = pd.DataFrame(data=d)
    df.boxplot()
    plt.title(label)
    plt.ylabel("ELBO")
    plt.savefig("brownian " +label+".pdf")
    plt.clf()
    #plt.show()


