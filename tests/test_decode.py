from release.olive.decode import DefaultDecoder, load_default_decoder


def test_default_decoder_deterministic_and_ordered():
    d = load_default_decoder(4)                      # eeg_priors/4/us1/eeg_pred_beta.json
    p_t1, q1 = d.decode(2, seed=12345)               # item_dtn=2 -> target
    p_t2, q2 = d.decode(2, seed=12345)
    p_nt, _  = d.decode(1, seed=12345)               # item_dtn=1 -> nontarget
    assert p_t1 == p_t2                               # deterministic under fixed seed
    assert 0.0 <= p_t1 <= 1.0 and 0.0 <= p_nt <= 1.0
    assert q1 == q2 and 0.4 <= q1 <= 1.0              # quality in expected AUC range
    assert p_t1 > p_nt                                # target prob higher on average/seed
