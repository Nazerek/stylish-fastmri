# -*- coding: utf-8 -*-
"""Vanilla_VAE.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1h9kiwLz1vWd5Lm4m-8Hs3VzjxuzBGjF_
"""

import torch
import torch.utils.data
from torch import nn
from torch import Tensor
import torch.nn.functional as F

def re_parameterize(mu: Tensor, log_var: Tensor) -> Tensor:
    """
    Re-parameterization trick to sample from N(mu, var) from
    N(0,1).
    :param mu: (Tensor) Mean of the latent Gaussian [B x D]
    :param log_var: (Tensor) Standard deviation of the latent Gaussian [B x D]
    :return: (Tensor) [B x D]
    """
    std = torch.exp(0.5 * log_var)
    eps = torch.randn_like(std)
    return eps * std + mu 

def reconstruction_loss(x, x_recon, distribution='gaussian'):
    batch_size = x.shape[0]
    assert batch_size != 0

    if distribution == 'bernoulli':
        recon_loss = F.binary_cross_entropy_with_logits(x_recon, x, reduction='sum').div(batch_size)
    elif distribution == 'gaussian':
        recon_loss = F.mse_loss(x_recon, x, reduction='sum').div(batch_size)
    else:
        raise ValueError('value error for `distribution` expected: {bernoulli, or gaussian}')

    return recon_loss

def kl_divergence(mu, log_var):
    batch_size = mu.shape[0]
    assert batch_size != 0
    if mu.data.ndimension() == 4:
        mu = mu.view(mu.size(0), mu.size(1))

    if log_var.data.ndimension() == 4:
        log_var = log_var.view(log_var.size(0), log_var.size(1))

    klds = -0.5 * (1 + log_var - mu.pow(2) - log_var.exp())
    total_kld = klds.sum(1).mean(0, True)
    dimension_wise_kld = klds.mean(0)
    mean_kld = klds.mean(1).mean(0, True)

    return total_kld, dimension_wise_kld, mean_kld
  
from abc import abstractmethod, ABCMeta
from torch import nn
import torch.nn.functional as F

class Encoder(metaclass=ABCMeta):
    def __init__(self):
        super(Encoder, self).__init__()
        pass

    @abstractmethod
    def forward(self, x):
        pass


class Decoder(metaclass=ABCMeta):
    def __init__(self):
        super(Decoder, self).__init__()
        pass

    @abstractmethod
    def forward(self, x):
        pass


class Bottleneck(metaclass=ABCMeta):
    def __init__(self):
        super(Bottleneck, self).__init__()
        pass

    @abstractmethod
    def forward(self, **kwargs):
        pass


class LossFunction(nn.Module, metaclass=ABCMeta):
    def __init__(self):
        super(LossFunction, self).__init__()

    @abstractmethod
    def __call__(self, *args, **kwargs):
        pass


class View(nn.Module):
    def __init__(self, size):
        super(View, self).__init__()
        self.size = size

    def forward(self, tensor):
        return tensor.view(self.size)
        
class VanillaVAEEncoder(Encoder, nn.Module):
    def __init__(self, z_dim=10, nc=3):
        super(VanillaVAEEncoder, self).__init__()

        self.encoder = nn.Sequential(
            nn.Conv2d(nc, 32, 4, 2, 1),  # B,  32, 32, 32
            nn.ReLU(True),
            nn.Conv2d(32, 32, 4, 2, 1),  # B,  32, 16, 16
            nn.ReLU(True),
            nn.Conv2d(32, 32, 4, 2, 1),  # B,  32,  8,  8
            nn.ReLU(True),
            nn.Conv2d(32, 32, 4, 2, 1),  # B,  32,  8,  8
            nn.ReLU(True),
            View((-1, 32 * 8 * 8)),  # B, 2048
            nn.Linear(32 * 8 * 8, 512),  # B, 512
            nn.ReLU(True),
            nn.Linear(512, 256),  # B, 256
            nn.ReLU(True),
            nn.Linear(256, z_dim),  # B, z_dim*2
        )

    def forward(self, x):
        return self.encoder(x)


class VanillaVAEDecoder(Decoder, nn.Module):
    def __init__(self, z_dim=10, nc=3, target_size=(128, 128)):
        super(VanillaVAEDecoder, self).__init__()
        self.target_size = target_size

        self.decoder = nn.Sequential(
            nn.Linear(z_dim, 256),  # B, 256
            nn.ReLU(True),
            nn.Linear(256, 256),  # B, 256
            nn.ReLU(True),
            nn.Linear(256, 32 * 8 * 8),  # B, 2048
            nn.ReLU(True),
            View((-1, 32, 8, 8)),  # B,  32,  8,  8
            nn.ConvTranspose2d(32, 32, 4, 2, 1),  # B,  32,  8,  8
            nn.ReLU(True),
            nn.ConvTranspose2d(32, 32, 4, 2, 1),  # B,  32, 16, 16
            nn.ReLU(True),
            nn.ConvTranspose2d(32, 32, 4, 2, 1),  # B,  32, 32, 32
            nn.ReLU(True),
            nn.ConvTranspose2d(32, nc, 4, 2, 1),  # B,  nc, 64, 64
            nn.Tanh(),
            View(self.target_size),
        )

    def forward(self, x):
        return self.decoder(x)


class VanillaVAEBottleneck(Bottleneck, nn.Module):
    def __init__(self, latent_dim):
        super(VanillaVAEBottleneck, self).__init__()
        self.mu = nn.Linear(latent_dim, latent_dim)
        self.var = nn.Linear(latent_dim, latent_dim)

    def forward(self, x):
        x = torch.flatten(x, start_dim=1)
        mu = self.mu(x)
        log_var = self.var(x)
        z = re_parameterize(mu, log_var)
        return z, mu, log_var


class VanillaVAE(nn.Module):
    def __init__(self, z_dim, nc, target_size):
        super(VanillaVAE, self).__init__()

        self.encoder = VanillaVAEEncoder(z_dim, nc)
        self.bottleneck = VanillaVAEBottleneck(z_dim)
        self.decoder = VanillaVAEDecoder(z_dim, nc, target_size)

    def forward(self, x):
        x = self.encoder(x)
        z, mu, log_var = self.bottleneck(x)
        x = self.decoder(z)
        return x, mu, log_var


class VanillaVAELossFunction(LossFunction):
    def __call__(self, x, x_recon, mu, log_var):
        recons_loss = reconstruction_loss(x_recon, x)
        total_kld, dim_wise_kld, mean_kld = kl_divergence(mu, log_var)
        return recons_loss + total_kld

