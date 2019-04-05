import math

import torch.optim as optim
from torch.utils.data.dataloader import DataLoader
from tqdm import tqdm

from SGD import *
from BayesBackpropagation import *
from data.dataset import MNISTDataset
from data.parser import parse_mnist
from data.transforms import MNISTTransform

class MNIST(object):
    def __init__(self, BATCH_SIZE, TEST_BATCH_SIZE, CLASSES, TRAIN_EPOCHS, SAMPLES, hasScalarMixturePrior, PI, SIGMA_1,
                 SIGMA_2, INPUT_SIZE, LAYERS, ACTIVATION_FUNCTIONS, LR, MODE='mlp', GOOGLE_INIT=False,
                 train_loader=None, valid_loader=None, test_loader=None):
        if train_loader is None or valid_loader is None or test_loader is None:
            # Prepare data
            if MODE == 'mlp':
                train_data, train_label, valid_data, valid_label, test_data, test_label = parse_mnist(2)
            elif MODE == 'cnn':
                train_data, train_label, valid_data, valid_label, test_data, test_label = parse_mnist(4)
            else:
                raise ValueError('Usupported mode')

            train_dataset = MNISTDataset(train_data, train_label, transform=MNISTTransform())
            valid_dataset = MNISTDataset(valid_data, valid_label, transform=MNISTTransform())
            test_dataset = MNISTDataset(test_data, test_label, transform=MNISTTransform())
            self.train_loader = DataLoader(train_dataset, BATCH_SIZE, shuffle=True, **LOADER_KWARGS)
            self.valid_loader = DataLoader(valid_dataset, TEST_BATCH_SIZE, shuffle=False, **LOADER_KWARGS)
            self.test_loader = DataLoader(test_dataset, TEST_BATCH_SIZE, shuffle=False, **LOADER_KWARGS)
        else:
            self.train_loader = train_loader
            self.valid_loader = valid_loader
            self.test_loader = test_loader

        # Hyper parameter setting
        self.TEST_BATCH_SIZE = TEST_BATCH_SIZE
        self.TRAIN_SIZE = len(self.train_loader.dataset)
        self.TEST_SIZE = len(self.test_loader.dataset)
        self.NUM_BATCHES = len(self.train_loader)
        self.NUM_TEST_BATCHES = len(self.test_loader)

        self.CLASSES = CLASSES
        self.TRAIN_EPOCHS = TRAIN_EPOCHS
        self.SAMPLES = SAMPLES

        # Checking if the mentioned batch sizes are feasible
        assert (self.TRAIN_SIZE % BATCH_SIZE) == 0
        assert (self.TEST_SIZE % TEST_BATCH_SIZE) == 0

        # Network Declaration
        self.net = BayesianNetwork(inputSize=INPUT_SIZE,
                                   CLASSES=CLASSES,
                                   layers=LAYERS,
                                   activations=ACTIVATION_FUNCTIONS,
                                   SAMPLES=SAMPLES,
                                   BATCH_SIZE=BATCH_SIZE,
                                   NUM_BATCHES=self.NUM_BATCHES,
                                   hasScalarMixturePrior=hasScalarMixturePrior,
                                   PI=PI,
                                   SIGMA_1=SIGMA_1,
                                   SIGMA_2=SIGMA_2,
                                   GOOGLE_INIT=GOOGLE_INIT).to(DEVICE)

        # Optimizer declaration
        self.optimizer = optim.SGD(self.net.parameters(), lr=LR)  # self.optimizer = optim.Adam(self.net.parameters())

    # Define the training step for MNIST data set
    def train(self, blundell_weighting = False):
        loss = 0.
        for batch_idx, (input, target) in enumerate(self.train_loader):
            input, target = input.to(DEVICE), target.to(DEVICE)
            self.net.zero_grad()
            if blundell_weighting:
                loss = self.net.BBB_loss(input, target, batch_idx)
            else:
                loss = self.net.BBB_loss(input, target)
            loss.backward()
            self.optimizer.step()
        return loss

    # Testing the ensemble
    def test(self, valid=True):
        data_loader = self.valid_loader if valid else self.test_loader
        correct = 0
        with torch.no_grad():
            for input, target in data_loader:
                input, target = input.to(DEVICE), target.to(DEVICE)
                output = self.net.forward(input, infer=True)
                pred = output.max(1, keepdim=True)[1]
                correct += pred.eq(target.view_as(pred)).sum().item()

        accuracy = correct / self.TEST_SIZE

        return round(100 * (1 - accuracy), 3)  # Error


# Multiple epochs
def multipleEpochAnalyis():
    # Hyperparameter declaration
    BATCH_SIZE = 125
    TEST_BATCH_SIZE = 1000
    CLASSES = 10
    TRAIN_EPOCHS = 600
    SAMPLES = 1
    PI = 0.75
    SIGMA_1 = torch.cuda.FloatTensor([math.exp(-0.)]) # torch.cuda.FloatTensor([0.75])
    SIGMA_2 = torch.cuda.FloatTensor([math.exp(-8.)]) # torch.cuda.FloatTensor([0.1])
    INPUT_SIZE = 28 * 28
    LAYERS = np.array([400, 400])
    LR = 1e-3
    GOOGLE_INIT = False

    # errorRate = []  # to store error rates at different epochs

    mnist = MNIST(BATCH_SIZE=BATCH_SIZE,
                  TEST_BATCH_SIZE=TEST_BATCH_SIZE,
                  CLASSES=CLASSES,
                  TRAIN_EPOCHS=TRAIN_EPOCHS,
                  SAMPLES=SAMPLES,
                  hasScalarMixturePrior=True,
                  PI=PI,
                  SIGMA_1=SIGMA_1,
                  SIGMA_2=SIGMA_2,
                  INPUT_SIZE=INPUT_SIZE,
                  LAYERS=LAYERS,
                  ACTIVATION_FUNCTIONS=np.array(['relu', 'relu', 'softmax']),
                  LR=LR,
                  GOOGLE_INIT=GOOGLE_INIT)

    for _ in tqdm(range(TRAIN_EPOCHS)):
        loss = mnist.train()
        validErr, testErr = mnist.test(valid=True), mnist.test(valid=False)
        print(validErr, testErr, float(loss))
        # errorRate.append(validErr)
        # np.savetxt('./Results/BBB_epochs_errorRate_blundell_1200_5samples.csv', np.asarray(errorRate), delimiter=",")

    # errorRate = np.asarray(errorRate)
    # plt.plot(range(TRAIN_EPOCHS), errorRate, c='royalblue', label='Bayes BackProp')
    # plt.legend()
    # plt.tight_layout()
    # plt.savefig('./Results/MNIST_EPOCHS.png')
    torch.save(mnist.net.state_dict(), './Models/BBB_MNIST.pth')


# Scalar Mixture vs Gaussian
def MixtureVsGaussianAnalyis():
    # Hyperparameter setting
    BATCH_SIZE = 125
    TEST_BATCH_SIZE = 1000
    CLASSES = 10
    SAMPLES = 2
    TRAIN_EPOCHS = 600
    PI = 0.5
    SIGMA_1 = torch.cuda.FloatTensor([math.exp(-0)])
    SIGMA_2 = torch.cuda.FloatTensor([math.exp(-6)])
    INPUT_SIZE = 28 * 28
    LAYERS = np.array([[400, 400], [800, 800], [1200, 1200]])  # Possible layer configuration
    reading = []

    for l in range(LAYERS.shape[0]):
        layer = np.asarray(LAYERS[l])
        print("Network architecture: ", layer)

        # one with scalar mixture gaussian prior
        mnist = MNIST(BATCH_SIZE=BATCH_SIZE,
                      TEST_BATCH_SIZE=TEST_BATCH_SIZE,
                      CLASSES=CLASSES,
                      TRAIN_EPOCHS=TRAIN_EPOCHS,
                      SAMPLES=SAMPLES,
                      hasScalarMixturePrior=True,
                      PI=PI,
                      SIGMA_1=SIGMA_1,
                      SIGMA_2=SIGMA_2,
                      INPUT_SIZE=INPUT_SIZE,
                      LAYERS=layer,
                      ACTIVATION_FUNCTIONS=np.array(['relu', 'relu', 'softmax']))

        # one with simple gaussian prior
        mnistGaussian = MNIST(BATCH_SIZE=BATCH_SIZE,
                              TEST_BATCH_SIZE=TEST_BATCH_SIZE,
                              CLASSES=CLASSES,
                              TRAIN_EPOCHS=TRAIN_EPOCHS,
                              SAMPLES=SAMPLES,
                              hasScalarMixturePrior=False,
                              PI=PI,
                              SIGMA_1=SIGMA_1,
                              SIGMA_2=SIGMA_2,
                              INPUT_SIZE=INPUT_SIZE,
                              LAYERS=layer,
                              ACTIVATION_FUNCTIONS=np.array(['relu', 'relu', 'softmax']))

        for _ in tqdm(range(TRAIN_EPOCHS)):
            mnist.train()
            mnistGaussian.train()
        print("Testing begins!")
        reading.append([layer[0], mnist.test(), mnistGaussian.test()])

    reading = np.asarray(reading)
    np.savetxt('./Results/BBB_scalarVsGaussian.csv', reading, delimiter=",")


# Different values of sample, pi, sigma 1 and sigma 2
def HyperparameterAnalysis():
    import sys
    samples = int(sys.argv[1])

    # hyper parameter declaration
    BATCH_SIZE = 125
    TEST_BATCH_SIZE = 1000
    CLASSES = 10
    TRAIN_EPOCHS = 10
    #SAMPLES = np.array([1, 2, 5, 10])  # possible values of sample size
    PI = np.array([0.25, 0.5, 0.75])  # possible values of pi
    SIGMA_1 = np.array([0, 1, 2])  # possible values of sigma1
    SIGMA_2 = np.array([6, 7, 8])  # possible values of sigma2
    INPUT_SIZE = 28 * 28
    LAYERS = np.array([400, 400])
    LR = [1e-3]

    errorRate = []
    #for sample in range(SAMPLES.size):
    for pi in range(PI.size):
            for sigma1 in range(SIGMA_1.size):
                for sigma2 in range(SIGMA_2.size):
                    for lr in range(len(LR)):

                        mnist = MNIST(BATCH_SIZE=BATCH_SIZE,
                                      TEST_BATCH_SIZE=TEST_BATCH_SIZE,
                                      CLASSES=CLASSES,
                                      TRAIN_EPOCHS=TRAIN_EPOCHS,
                                      SAMPLES=samples,
                                      hasScalarMixturePrior=True,
                                      PI=PI[pi],
                                      SIGMA_1=torch.cuda.FloatTensor([math.exp(-SIGMA_1[sigma1])]),
                                      SIGMA_2=torch.cuda.FloatTensor([math.exp(-SIGMA_2[sigma2])]),
                                      INPUT_SIZE=INPUT_SIZE,
                                      LAYERS=LAYERS,
                                      ACTIVATION_FUNCTIONS=np.array(['relu', 'relu', 'softmax']),
                                      LR=LR[lr])

                        print(samples, PI[pi], SIGMA_1[sigma1], SIGMA_2[sigma2], LR[lr])

                        acc = 0.
                        for epoch in tqdm(range(TRAIN_EPOCHS)):
                            mnist.train()
                            acc = mnist.test()
                            errorRate.append(
                                [samples, PI[pi], SIGMA_1[sigma1], SIGMA_2[sigma2], LR[lr], epoch + 1, acc])
                            np.savetxt('./Results/BBB_hyperparameters_samples' + str(samples) + '.csv', errorRate,
                                       delimiter=",")
                        print(acc)

def classify(MODEL, HIDDEN_UNITS, TRAIN_EPOCHS, DATASET, BATCH_SIZE=125, TEST_BATCH_SIZE=1000):
    """Set model"""
    if DATASET == 'mnist':
        train_data, train_label, valid_data, valid_label, test_data, test_label = parse_mnist(2)

        train_dataset = MNISTDataset(train_data, train_label, transform=MNISTTransform())
        valid_dataset = MNISTDataset(valid_data, valid_label, transform=MNISTTransform())
        test_dataset = MNISTDataset(test_data, test_label, transform=MNISTTransform())
        train_loader = DataLoader(train_dataset, BATCH_SIZE, shuffle=True, **LOADER_KWARGS)
        valid_loader = DataLoader(valid_dataset, TEST_BATCH_SIZE, shuffle=False, **LOADER_KWARGS)
        test_loader = DataLoader(test_dataset, TEST_BATCH_SIZE, shuffle=False, **LOADER_KWARGS)

        INPUT_SIZE = 28 * 28
        CLASSES = 10
    else:
        raise ValueError('Valid params: DATASET=mnist')

    if MODEL== 'bbb':
        # Define the used hyperparameters
        if HIDDEN_UNITS==400:
            SAMPLES = 1
            PI = 0.75
            SIGMA_1 = 1.
            SIGMA_2 = 6.
            LR = 1e-3
            GOOGLE_INIT = False
            BLUNDELL_WEIGHTING = False
        elif HIDDEN_UNITS==800:
            SAMPLES = 1
            PI = 0.75
            SIGMA_1 = 1.
            SIGMA_2 = 6.
            LR = 1e-3
            GOOGLE_INIT = False
            BLUNDELL_WEIGHTING = False
        elif HIDDEN_UNITS==1200:
            SAMPLES = 1
            PI = 0.75
            SIGMA_1 = 0.
            SIGMA_2 = 7.
            LR = 1e-4
            GOOGLE_INIT = False
            BLUNDELL_WEIGHTING = False
        else:
            raise ValueError('Valid params: HIDDEN_UNITS=400|800|1200')
        LAYERS = np.array([HIDDEN_UNITS, HIDDEN_UNITS])

        # errorRate = []  # to store error rates at different epochs

        mnist = MNIST(BATCH_SIZE=BATCH_SIZE,
                      TEST_BATCH_SIZE=TEST_BATCH_SIZE,
                      CLASSES=CLASSES,
                      TRAIN_EPOCHS=TRAIN_EPOCHS,
                      SAMPLES=SAMPLES,
                      hasScalarMixturePrior=True,
                      PI=PI,
                      SIGMA_1=torch.FloatTensor([math.exp(-SIGMA_1)]).to(DEVICE),
                      SIGMA_2=torch.FloatTensor([math.exp(-SIGMA_2)]).to(DEVICE),
                      INPUT_SIZE=INPUT_SIZE,
                      LAYERS=LAYERS,
                      ACTIVATION_FUNCTIONS=np.array(['relu', 'relu', 'softmax']),
                      LR=LR,
                      GOOGLE_INIT=GOOGLE_INIT,
                      train_loader=train_loader,
                      test_loader=test_loader,
                      valid_loader=valid_loader)

        train_losses = np.zeros(TRAIN_EPOCHS)
        valid_errs = np.zeros(TRAIN_EPOCHS)
        test_errs = np.zeros(TRAIN_EPOCHS)

        for epoch in tqdm(range(TRAIN_EPOCHS)):
            loss = mnist.train(blundell_weighting=BLUNDELL_WEIGHTING)
            validErr, testErr = mnist.test(valid=True), mnist.test(valid=False)

            print(validErr, testErr, float(loss))

            valid_errs[epoch] = validErr
            test_errs[epoch] = testErr
            train_losses[epoch] = float(loss)

        # Save results
        torch.save(mnist.net.state_dict(), './Models/BBB_MNIST.pth')

        path = 'Results/BBB_MNIST_' + str(HIDDEN_UNITS)
        wr = csv.writer(open(path + '.csv', 'w'), delimiter=',', lineterminator='\n')
        wr.writerow(['epoch', 'valid_acc', 'test_acc', 'train_losses'])
        for i in range(max_epoch):
            wr.writerow((i + 1, valid_errs[i], test_errs[i], train_losses[i]))
    elif MODEL=='dropout' or MODEL=='mlp':
        hyper = SGD_Hyper()
        hyper.hidden_units = HIDDEN_UNITS
        hyper.max_epoch = TRAIN_EPOCHS
        hyper.mode = MODEL

        # Train and save results
        SGD_run(hyper, train_loader=train_loader, test_loader=test_loader, valid_loader=valid_loader)


if __name__ == '__main__':
    # multipleEpochAnalyis()
    # MixtureVsGaussianAnalyis()
    # HyperparameterAnalysis()

    classify(MODEL='dropout', HIDDEN_UNITS=400, TRAIN_EPOCHS=600, DATASET='mnist')