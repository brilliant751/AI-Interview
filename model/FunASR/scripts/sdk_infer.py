import argparse

from funasr import AutoModel


def main() -> None:
    parser = argparse.ArgumentParser(description="FunASR SDK quick inference")
    parser.add_argument("--audio", required=True, help="path to local wav/mp3 file")
    parser.add_argument("--model", default="paraformer-zh")
    parser.add_argument("--vad-model", default="fsmn-vad")
    parser.add_argument("--punc-model", default="ct-punc")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    model = AutoModel(
        model=args.model,
        vad_model=args.vad_model,
        punc_model=args.punc_model,
        device=args.device,
    )

    result = model.generate(input=args.audio, batch_size_s=300)
    print(result)


if __name__ == "__main__":
    main()
