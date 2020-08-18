import argparse
import logging
import os
from glob import glob
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

# from unet.model import Modified2DUNet as UNet
# from unet.model_level3_withsigmoidfordiceloss import Modified2DUNet as UNet
from unet.model_level3_dl_dilationCov_transConv import Modified2DUNet as UNet
from nni.compression.torch import apply_compression_results, ModelSpeedup


from utils.data_vis import plot_img_and_mask
from utils.dataset import BasicDataset
resize = False
# resize = True
size = (900,1440)


#袋鼠剧增强的测试
def predict_img(net,
                full_img,
                device,
                scale_factor=1,
                out_threshold=0.3):
    net.eval()

    img = torch.from_numpy(BasicDataset.preprocess(full_img, scale_factor))

    img = img.unsqueeze(0)
    img = img.to(device=device, dtype=torch.float32)

    with torch.no_grad():
        output = net(img)

        probs = output.squeeze(0)

        tf = transforms.Compose(
            [
                transforms.ToPILImage(),
                transforms.Resize(size if resize else full_img.size[1]),
                # transforms.Resize(full_img.size[1]),
                transforms.ToTensor()
            ]
        )
        probs = tf(probs.cpu())
        full_mask = probs.squeeze().cpu().numpy()

    return full_mask > out_threshold


def get_args():
    parser = argparse.ArgumentParser(description='Predict masks from input images',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--model', '-m', default='MODEL.pth',
                        metavar='FILE',
                        help="Specify the file in which the model is stored")
    parser.add_argument('--input', '-i', metavar='INPUT', nargs='+',
                        help='filenames of input images')

    parser.add_argument('--output', '-o', metavar='INPUT', nargs='+',
                        help='Filenames of ouput images')
    parser.add_argument('--viz', '-v', action='store_true',
                        help="Visualize the images as they are processed",
                        default=False)
    parser.add_argument('--no-save', '-n', action='store_true',
                        help="Do not save the output masks",
                        default=False)
    parser.add_argument('--mask-threshold', '-t', type=float,
                        help="Minimum probability value to consider a mask pixel white",
                        default=0.1)
    parser.add_argument('--scale', '-s', type=float,
                        help="Scale factor for the input images",
                        default=1)

    return parser.parse_args()


def get_output_filenames(in_files):
    out_files = []

    if not args.output:
        for f in in_files:
            pathsplit = os.path.splitext(f)
            out_files.append("{}_OUT{}".format(pathsplit[0], pathsplit[1]))
    elif len(in_files) != len(args.output):
        logging.error("Input files and output files are not of the same length")
        raise SystemExit()
    else:
        out_files = args.output

    return out_files


def mask_to_image(mask):
    return Image.fromarray((mask * 255).astype(np.uint8))


if __name__ == "__main__":
    args = get_args()

    #要预测的图片路径
    args.input = glob('./data/val/*')
    # 输出路径
    out_path = './data/predict/'

    in_files = args.input
    out_files = get_output_filenames(in_files)


    logging.info("Loading model {}".format(args.model))

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    # logging.info(f'Using device {device}')
    #选择要加载的模型

    net = torch.load('./save_pruner/speedup_model.pt')
    net.to(device=device)

    logging.info("Model loaded !")
    net.eval()

    import time

    start = time.time()
    for i, fn in enumerate(in_files):
        logging.info("\nPredicting image {} ...".format(fn))

        img = Image.open(fn)

        mask = predict_img(net=net,
                           full_img=img,
                           scale_factor=args.scale,
                           out_threshold=args.mask_threshold,
                           device=device)
    print('elapsed time when use speedup: ', time.time() - start)

        # if not args.no_save:

        #     if not os.path.exists(out_path):
        #         os.mkdir(out_path)
        #     out_fn = os.path.abspath(out_path + os.path.basename(fn)[:-4]+'out'+'.jpg')
        #     result = mask_to_image(mask)
        #     result.save(out_fn)

        #     logging.info("Mask saved to {}".format(out_files[i]))

        # if args.viz:
        #     logging.info("Visualizing results for image {}, close to continue ...".format(fn))
        #     plot_img_and_mask(img, mask)