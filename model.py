import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchvision.models as models
import copy

import config
import cv2
import utils
class ContentLoss(nn.Module):

    def __init__(self, target,):
        super(ContentLoss, self).__init__()
        # we 'detach' the target content from the tree used
        # to dynamically compute the gradient: this is a stated value,
        # not a variable. Otherwise the forward method of the criterion
        # will throw an error.
        self.target = target.detach()

    def forward(self, input):
        #print('*************: ', input.size(), self.target.size())
        self.loss = F.mse_loss(input, self.target)
        return input


def gram_matrix(input):
    a, b, c, d = input.size()  # a = batch size (=1)
    # b = number of feature maps
    # (c, d) = dimensions of a f. map (N=c*d)

    features = input.view(a*b, c*d)

    G = torch.mm(features, features.t())  # compute the gram product

    # we 'normalize' the values of the gram matrix
    # by dividing by the number of element in each feature maps.
    return G.div(2 * a * b * c *d)

'''
class StyleLoss(nn.Module):

    def __init__(self, target_feature, a, b):
        super(StyleLoss, self).__init__()
        self.target = gram_matrix(target_feature).detach()

    def forward(self, input):
        G = gram_matrix(input)
        self.loss = F.mse_loss(G, self.target)
        return input
'''

class StyleLoss(nn.Module):

    def __init__(self, target_feature, style_mask, content_mask):
        super(StyleLoss, self).__init__()

        self.style_mask = style_mask.clone()
        self.content_mask = content_mask.clone()

        #print(target_feature.type(), mask.type())
        _, channel_f, height, width = target_feature.size()
        channel = self.style_mask.size()[0]
        
        # ********
<<<<<<< HEAD
        xc = torch.linspace(-1, 1, width).repeat(height, 1)
        yc = torch.linspace(-1, 1, height).view(-1, 1).repeat(1, width)
        grid = torch.cat((xc.unsqueeze(2), yc.unsqueeze(2)), 2) 
        grid = grid.unsqueeze_(0).to(config.device0)
        mask_ = F.grid_sample(self.style_mask.unsqueeze(0), grid).squeeze(0)
=======
        temp_style_mask = self.style_mask.permute(1, 2, 0)
        mask_ = utils.bilinear_interpolate_torch(temp_style_mask, 
                                                 torch.FloatTensor(height).type(torch.cuda.FloatTensor), 
                                                 torch.FloatTensor(width).type(torch.cuda.FloatTensor))
        mask_ = mask_.permute(2, 0, 1)
>>>>>>> d8bf45d512847097a87b547b239243086de6a4d6
        # ********       
        #mask_ = self.style_mask.data.resize_(channel, height, width).clone()
        target_feature_3d = target_feature.squeeze(0).clone()
        size_of_mask = (channel, channel_f, height, width)
        target_feature_masked = torch.zeros(size_of_mask, dtype=torch.float).to(config.device0)
        for i in range(channel):
            target_feature_masked[i, :, :, :] = mask_[i, :, :] * target_feature_3d

        self.targets = list()
        for i in range(channel):
            temp = target_feature_masked[i, :, :, :]
            self.targets.append( gram_matrix(temp.unsqueeze(0)).detach() )

    def forward(self, input_feature):
        self.loss = 0
        _, channel_f, height, width = input_feature.size()
        channel = self.content_mask.size()[0]
        # ****
<<<<<<< HEAD
        xc = torch.linspace(-1, 1, width).repeat(height, 1)
        yc = torch.linspace(-1, 1, height).view(-1, 1).repeat(1, width)
        grid = torch.cat((xc.unsqueeze(2), yc.unsqueeze(2)), 2)
        grid = grid.unsqueeze_(0).to(config.device0)
        mask = F.grid_sample(self.content_mask.unsqueeze(0), grid).squeeze(0)
=======
        temp_content_mask = self.content_mask.permute(1, 2, 0)
        mask = utils.bilinear_interpolate_torch(temp_content_mask, 
                                                torch.FloatTensor(height).type(torch.cuda.FloatTensor), 
                                                torch.FloatTensor(width).type(torch.cuda.FloatTensor))
        mask = mask.permute(2, 0, 1)
>>>>>>> d8bf45d512847097a87b547b239243086de6a4d6
        # ****
        #mask = self.content_mask.data.resize_(channel, height, width).clone()
        input_feature_3d = input_feature.squeeze(0).clone()
        size_of_mask = (channel, channel_f, height, width)
        input_feature_masked = torch.zeros(size_of_mask, dtype=torch.float32).to(config.device0)
        for i in range(channel):
            input_feature_masked[i, :, :, :] = mask[i, :, :] * input_feature_3d

        inputs_G = list()
        for i in range(channel):
            temp = input_feature_masked[i, :, :, :]
            inputs_G.append( gram_matrix(temp.unsqueeze(0)) )

        for i in range(channel):
            self.loss += F.mse_loss(inputs_G[i], self.targets[i])
        
        return input_feature

class TVLoss(nn.Module):

    def __init__(self):
        super(TVLoss, self).__init__()
        self.ky = np.array([
            [[0, 0, 0],[0, 1, 0],[0,-1, 0]],
            [[0, 0, 0],[0, 1, 0],[0,-1, 0]],
            [[0, 0, 0],[0, 1, 0],[0,-1, 0]]
        ])
        self.kx = np.array([
            [[0, 0, 0],[0, 1,-1],[0, 0, 0]],
            [[0, 0, 0],[0, 1,-1],[0, 0, 0]],
            [[0, 0, 0],[0, 1,-1],[0, 0, 0]]
        ])
        self.conv_x = nn.Conv2d(1, 1, kernel_size=3, stride=1, padding=1, bias=False)
        self.conv_x.weight = nn.Parameter(torch.from_numpy(self.kx).float().unsqueeze(0).to(config.device0),
                                          requires_grad=False)
        self.conv_y = nn.Conv2d(1, 1, kernel_size=3, stride=1, padding=1, bias=False)
        self.conv_y.weight = nn.Parameter(torch.from_numpy(self.ky).float().unsqueeze(0).to(config.device0),
                                          requires_grad=False)

    def forward(self, input):
        height, width = input.size()[2:4]
        gx = self.conv_x(input)
        gy = self.conv_y(input)

        # gy = gy.squeeze(0).squeeze(0)
        # cv2.imwrite('gy.png', (gy*255.0).to('cpu').numpy().astype('uint8'))
        # exit()

        self.loss = torch.sum(gx**2 + gy**2)/(height * width)
        return input

# create a module to normalize input image so we can easily put it in a
# nn.Sequential
class Normalization(nn.Module):
    def __init__(self, mean, std):
        super(Normalization, self).__init__()
        # .view the mean and std to make them [C x 1 x 1] so that they can
        # directly work with image Tensor of shape [B x C x H x W].
        # B is batch size. C is number of channels. H is height and W is width.
        self.mean = torch.tensor(mean).view(-1, 1, 1)
        self.std = torch.tensor(std).view(-1, 1, 1)

    def forward(self, img):
        # normalize img
        return (img - self.mean) / self.std


# desired depth layers to compute style/content losses:
content_layers_default = ['conv_4'] 
style_layers_default = ['conv_1', 'conv_2', 'conv_3', 'conv_4', 'conv_5']
def get_style_model_and_losses(cnn, normalization_mean, normalization_std,
                               style_img, content_img, style_mask, content_mask,
                               content_layer= content_layers_default,
                               style_layers=style_layers_default):
    cnn = copy.deepcopy(cnn)

    # normalization module
    normalization = Normalization(normalization_mean, normalization_std).to(config.device0)

    # just in order to have an iterable access to or list of content.style losses
    content_losses = []
    style_losses = []
    tv_losses = []

    # assuming that cnn is a nn.Sequential, so we make a new nn. Sequential
    # to put in modules that are supposed to be activated sequentially
    model = nn.Sequential(normalization)
    tv_loss = TVLoss()
    model.add_module("tv_loss_{}".format(0), tv_loss)
    tv_losses.append(tv_loss)
    i = 0 # increment every time we see a conv layer
    for layer in cnn.children():          # cnn feature  是没有 全连接层的
        if isinstance(layer, nn.Conv2d):
            i += 1
            name = 'conv_{}'.format(i)
        elif isinstance(layer, nn.ReLU):
            name = 'relu_{}'.format(i)
            # The in-place version doesn't play very nicely with the ContentLoss
            # and StyleLoss we insert below. So we replace with out-of-place
            # ones here.
            layer = nn.ReLU(inplace=False)
        elif isinstance(layer, nn.MaxPool2d):
            name = 'pool_{}'.format(i)
        elif isinstance(layer, nn.BatchNorm2d):
            name = 'bn_{}'.format(i)
        else:
            raise RuntimeError('Unrecognized layer: {}'.format(layer.__class__.__name__))

        model.add_module(name, layer)

        if name in content_layer:
            # add content loss
            print('xixi: ', content_img.size())
            target = model(content_img).detach()
            print('content target size: ', target.size())
            content_loss = ContentLoss(target)
            model.add_module("content_loss_{}".format(i), content_loss)
            content_losses.append(content_loss)

        if name in style_layers:
            # add style loss:
            print('style_:', style_img.type())
            target_feature = model(style_img).detach()
            style_loss = StyleLoss(target_feature, style_mask.detach(), content_mask.detach())
            model.add_module("style_loss_{}".format(i), style_loss)
            style_losses.append(style_loss)

    # now we trim off the layers after the last content and style losses
    for i in range(len(model)-1, -1, -1):
        if isinstance(model[i], ContentLoss) or isinstance(model[i], StyleLoss):
            break

    model = model[:(i+1)]

    return model, style_losses, content_losses, tv_losses


def get_input_optimizer(input_img):
    # this line to show that input is a parameter that requires a gradient
<<<<<<< HEAD
    # optimizer = optim.LBFGS([input_img.requires_grad_()], max_iter=1000, lr=0.1)
    optimizer = optim.Adadelta([input_img.requires_grad_()])
=======
    optimizer = optim.LBFGS([input_img.requires_grad_()], max_iter=1000, lr=0.1)
>>>>>>> d8bf45d512847097a87b547b239243086de6a4d6
    return optimizer

def run_style_transfer(cnn, normalization_mean, normalization_std,
                       content_img, style_img, input_img, style_mask, content_mask,
<<<<<<< HEAD
                       num_steps=12500000,
                       style_weight=50000, content_weight=1, tv_weight=0.001):
=======
                       num_steps=12500,
                       style_weight=1000000, content_weight=1, tv_weight=0.001):
>>>>>>> d8bf45d512847097a87b547b239243086de6a4d6

    """Run the style transfer."""
    print("Buliding the style transfer model..")
    model, style_losses, content_losses, tv_losses = get_style_model_and_losses(cnn,
        normalization_mean, normalization_std, style_img, content_img, style_mask, content_mask)
    optimizer = get_input_optimizer(input_img)

    print("Optimizing...")

    run = [0]
    while run[0] <= num_steps:

        def closure():
            # correct the values of updated input image
            input_img.data.clamp_(0, 1)
            optimizer.zero_grad()
            model(input_img)
            style_score = 0
            content_score = 0
            tv_score = 0
            weights_s = [0.2, 0.2, 0.2, 0.2, 0.2]
            for ii, sl in enumerate(style_losses):
                style_score += weights_s[ii]*sl.loss
            for cl in content_losses:
                content_score += cl.loss
            for tl in tv_losses:
                tv_score += tl.loss

            style_score *= style_weight
            content_score *= content_weight
            tv_score *= tv_weight

            loss = style_score + content_score + tv_score
            loss.backward()

            run[0] += 1
            if run[0] % 50 == 0:
                print("run {}:".format(run))
                print('Style Loss: {:4f} Content Loss: {:4f} TV Loss: {:4f}'.format(
                    style_score.item(), content_score.item(), tv_score.item()
                ))
                print()
                saved_img = input_img.clone()
                saved_img.data.clamp_(0, 1)
<<<<<<< HEAD
                utils.save_pic(saved_img, 7000000+run[0])
=======
                utils.save_pic(saved_img, run[0])
>>>>>>> d8bf45d512847097a87b547b239243086de6a4d6
            return style_score + content_score

        optimizer.step(closure)
        
    # a last corrention...
    input_img.data.clamp_(0, 1)
    
    return input_img



