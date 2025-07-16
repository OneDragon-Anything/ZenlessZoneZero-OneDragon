import cv2
import numpy as np
import math
from PIL import Image


from onnxocr.rec_postprocess import CTCLabelDecode
from onnxocr.predict_base import PredictBase

class TextRecognizer(PredictBase):
    def __init__(self, args):
        self.rec_image_shape = [int(v) for v in args.rec_image_shape.split(",")]
        self.rec_batch_num = args.rec_batch_num
        self.rec_algorithm = args.rec_algorithm
        self.postprocess_op = CTCLabelDecode(
            character_dict_path=args.rec_char_dict_path,
            use_space_char=args.use_space_char,
        )

        # 初始化模型
        self.rec_onnx_session = self.get_onnx_session(args.rec_model_dir, args.use_gpu)
        self.rec_input_name = self.get_input_name(self.rec_onnx_session)
        self.rec_output_name = self.get_output_name(self.rec_onnx_session)

    def resize_norm_img(self, img, max_wh_ratio):
        imgC, imgH, imgW = self.rec_image_shape
        if self.rec_algorithm == "NRTR" or self.rec_algorithm == "ViTSTR":
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # return padding_im
            image_pil = Image.fromarray(np.uint8(img))
            if self.rec_algorithm == "ViTSTR":
                img = image_pil.resize([imgW, imgH], Image.BICUBIC)
            else:
                img = image_pil.resize([imgW, imgH], Image.ANTIALIAS)
            img = np.array(img)
            norm_img = np.expand_dims(img, -1)
            norm_img = norm_img.transpose((2, 0, 1))
            if self.rec_algorithm == "ViTSTR":
                norm_img = norm_img.astype(np.float32) / 255.0
            else:
                norm_img = norm_img.astype(np.float32) / 128.0 - 1.0
            return norm_img
        elif self.rec_algorithm == "RFL":
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            resized_image = cv2.resize(img, (imgW, imgH), interpolation=cv2.INTER_CUBIC)
            resized_image = resized_image.astype("float32")
            resized_image = resized_image / 255
            resized_image = resized_image[np.newaxis, :]
            resized_image -= 0.5
            resized_image /= 0.5
            return resized_image

        assert imgC == img.shape[2]
        imgW = int((imgH * max_wh_ratio))

        # w = self.rec_onnx_session.get_inputs()[0].shape[3:][0]
        # w = self.rec_onnx_session.get_inputs()[0].shape[3:][0]
        # print(w)
        # if w is not None and w > 0:
        #     imgW = w

        h, w = img.shape[:2]
        ratio = w / float(h)
        if math.ceil(imgH * ratio) > imgW:
            resized_w = imgW
        else:
            resized_w = int(math.ceil(imgH * ratio))
        if self.rec_algorithm == "RARE":
            if resized_w > self.rec_image_shape[2]:
                resized_w = self.rec_image_shape[2]
            imgW = self.rec_image_shape[2]
        resized_image = cv2.resize(img, (resized_w, imgH))
        resized_image = resized_image.astype("float32")
        resized_image = resized_image.transpose((2, 0, 1)) / 255
        resized_image -= 0.5
        resized_image /= 0.5
        padding_im = np.zeros((imgC, imgH, imgW), dtype=np.float32)
        padding_im[:, :, 0:resized_w] = resized_image
        return padding_im

    def resize_norm_img_vl(self, img, image_shape):

        imgC, imgH, imgW = image_shape
        img = img[:, :, ::-1]  # bgr2rgb
        resized_image = cv2.resize(img, (imgW, imgH), interpolation=cv2.INTER_LINEAR)
        resized_image = resized_image.astype("float32")
        resized_image = resized_image.transpose((2, 0, 1)) / 255
        return resized_image

    def resize_norm_img_srn(self, img, image_shape):
        imgC, imgH, imgW = image_shape

        img_black = np.zeros((imgH, imgW))
        im_hei = img.shape[0]
        im_wid = img.shape[1]

        if im_wid <= im_hei * 1:
            img_new = cv2.resize(img, (imgH * 1, imgH))
        elif im_wid <= im_hei * 2:
            img_new = cv2.resize(img, (imgH * 2, imgH))
        elif im_wid <= im_hei * 3:
            img_new = cv2.resize(img, (imgH * 3, imgH))
        else:
            img_new = cv2.resize(img, (imgW, imgH))

        img_np = np.asarray(img_new)
        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        img_black[:, 0 : img_np.shape[1]] = img_np
        img_black = img_black[:, :, np.newaxis]

        row, col, c = img_black.shape
        c = 1

        return np.reshape(img_black, (c, row, col)).astype(np.float32)

    def srn_other_inputs(self, image_shape, num_heads, max_text_length):

        imgC, imgH, imgW = image_shape
        feature_dim = int((imgH / 8) * (imgW / 8))

        encoder_word_pos = (
            np.array(range(0, feature_dim)).reshape((feature_dim, 1)).astype("int64")
        )
        gsrm_word_pos = (
            np.array(range(0, max_text_length))
            .reshape((max_text_length, 1))
            .astype("int64")
        )

        gsrm_attn_bias_data = np.ones((1, max_text_length, max_text_length))
        gsrm_slf_attn_bias1 = np.triu(gsrm_attn_bias_data, 1).reshape(
            [-1, 1, max_text_length, max_text_length]
        )
        gsrm_slf_attn_bias1 = np.tile(gsrm_slf_attn_bias1, [1, num_heads, 1, 1]).astype(
            "float32"
        ) * [-1e9]

        gsrm_slf_attn_bias2 = np.tril(gsrm_attn_bias_data, -1).reshape(
            [-1, 1, max_text_length, max_text_length]
        )
        gsrm_slf_attn_bias2 = np.tile(gsrm_slf_attn_bias2, [1, num_heads, 1, 1]).astype(
            "float32"
        ) * [-1e9]

        encoder_word_pos = encoder_word_pos[np.newaxis, :]
        gsrm_word_pos = gsrm_word_pos[np.newaxis, :]

        return [
            encoder_word_pos,
            gsrm_word_pos,
            gsrm_slf_attn_bias1,
            gsrm_slf_attn_bias2,
        ]

    def process_image_srn(self, img, image_shape, num_heads, max_text_length):
        norm_img = self.resize_norm_img_srn(img, image_shape)
        norm_img = norm_img[np.newaxis, :]

        [encoder_word_pos, gsrm_word_pos, gsrm_slf_attn_bias1, gsrm_slf_attn_bias2] = (
            self.srn_other_inputs(image_shape, num_heads, max_text_length)
        )

        gsrm_slf_attn_bias1 = gsrm_slf_attn_bias1.astype(np.float32)
        gsrm_slf_attn_bias2 = gsrm_slf_attn_bias2.astype(np.float32)
        encoder_word_pos = encoder_word_pos.astype(np.int64)
        gsrm_word_pos = gsrm_word_pos.astype(np.int64)

        return (
            norm_img,
            encoder_word_pos,
            gsrm_word_pos,
            gsrm_slf_attn_bias1,
            gsrm_slf_attn_bias2,
        )

    def resize_norm_img_sar(self, img, image_shape, width_downsample_ratio=0.25):
        imgC, imgH, imgW_min, imgW_max = image_shape
        h = img.shape[0]
        w = img.shape[1]
        valid_ratio = 1.0
        # make sure new_width is an integral multiple of width_divisor.
        width_divisor = int(1 / width_downsample_ratio)
        # resize
        ratio = w / float(h)
        resize_w = math.ceil(imgH * ratio)
        if resize_w % width_divisor != 0:
            resize_w = round(resize_w / width_divisor) * width_divisor
        if imgW_min is not None:
            resize_w = max(imgW_min, resize_w)
        if imgW_max is not None:
            valid_ratio = min(1.0, 1.0 * resize_w / imgW_max)
            resize_w = min(imgW_max, resize_w)
        resized_image = cv2.resize(img, (resize_w, imgH))
        resized_image = resized_image.astype("float32")
        # norm
        if image_shape[0] == 1:
            resized_image = resized_image / 255
            resized_image = resized_image[np.newaxis, :]
        else:
            resized_image = resized_image.transpose((2, 0, 1)) / 255
        resized_image -= 0.5
        resized_image /= 0.5
        resize_shape = resized_image.shape
        padding_im = -1.0 * np.ones((imgC, imgH, imgW_max), dtype=np.float32)
        padding_im[:, :, 0:resize_w] = resized_image
        pad_shape = padding_im.shape

        return padding_im, resize_shape, pad_shape, valid_ratio

    def resize_norm_img_spin(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # return padding_im
        img = cv2.resize(img, tuple([100, 32]), cv2.INTER_CUBIC)
        img = np.array(img, np.float32)
        img = np.expand_dims(img, -1)
        img = img.transpose((2, 0, 1))
        mean = [127.5]
        std = [127.5]
        mean = np.array(mean, dtype=np.float32)
        std = np.array(std, dtype=np.float32)
        mean = np.float32(mean.reshape(1, -1))
        stdinv = 1 / np.float32(std.reshape(1, -1))
        img -= mean
        img *= stdinv
        return img

    def resize_norm_img_svtr(self, img, image_shape):

        imgC, imgH, imgW = image_shape
        resized_image = cv2.resize(img, (imgW, imgH), interpolation=cv2.INTER_LINEAR)
        resized_image = resized_image.astype("float32")
        resized_image = resized_image.transpose((2, 0, 1)) / 255
        resized_image -= 0.5
        resized_image /= 0.5
        return resized_image

    def resize_norm_img_abinet(self, img, image_shape):

        imgC, imgH, imgW = image_shape

        resized_image = cv2.resize(img, (imgW, imgH), interpolation=cv2.INTER_LINEAR)
        resized_image = resized_image.astype("float32")
        resized_image = resized_image / 255.0

        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        resized_image = (resized_image - mean[None, None, ...]) / std[None, None, ...]
        resized_image = resized_image.transpose((2, 0, 1))
        resized_image = resized_image.astype("float32")

        return resized_image

    def norm_img_can(self, img, image_shape):

        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # CAN only predict gray scale image

        if self.inverse:
            img = 255 - img

        if self.rec_image_shape[0] == 1:
            h, w = img.shape
            _, imgH, imgW = self.rec_image_shape
            if h < imgH or w < imgW:
                padding_h = max(imgH - h, 0)
                padding_w = max(imgW - w, 0)
                img_padded = np.pad(
                    img,
                    ((0, padding_h), (0, padding_w)),
                    "constant",
                    constant_values=(255),
                )
                img = img_padded

        img = np.expand_dims(img, 0) / 255.0  # h,w,c -> c,h,w
        img = img.astype("float32")

        return img

    def __call__(self, img_list):
        img_num = len(img_list)
        # Calculate the aspect ratio of all text bars
        width_list = []
        for img in img_list:
            width_list.append(img.shape[1] / float(img.shape[0]))
        # Sorting can speed up the recognition process
        indices = np.argsort(np.array(width_list))
        rec_res = [["", 0.0]] * img_num
        batch_num = self.rec_batch_num

        for beg_img_no in range(0, img_num, batch_num):
            end_img_no = min(img_num, beg_img_no + batch_num)
            norm_img_batch = []
            imgC, imgH, imgW = self.rec_image_shape[:3]
            max_wh_ratio = imgW / imgH
            # max_wh_ratio = 0
            for ino in range(beg_img_no, end_img_no):
                h, w = img_list[indices[ino]].shape[0:2]
                wh_ratio = w * 1.0 / h
                max_wh_ratio = max(max_wh_ratio, wh_ratio)
            for ino in range(beg_img_no, end_img_no):
                norm_img = self.resize_norm_img(img_list[indices[ino]], max_wh_ratio)
                norm_img = norm_img[np.newaxis, :]
                norm_img_batch.append(norm_img)

            norm_img_batch = np.concatenate(norm_img_batch)
            norm_img_batch = norm_img_batch.copy()

            # img = img[:, :, ::-1].transpose(2, 0, 1)
            # img = img[:, :, ::-1]
            # img = img.transpose(2, 0, 1)
            # img = img.astype(np.float32)
            # img = np.expand_dims(img, axis=0)
            # print(img.shape)
            input_feed = self.get_input_feed(self.rec_input_name, norm_img_batch)
            outputs = self.rec_onnx_session.run(
                self.rec_output_name, input_feed=input_feed
            )

            preds = outputs[0]

            rec_result = self.postprocess_op(preds)
            for rno in range(len(rec_result)):
                rec_res[indices[beg_img_no + rno]] = rec_result[rno]

        return rec_res
