// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import { OFT } from "../../contracts/oft/OFT.sol";
import { SendParam } from "../../contracts/oft/OFTCore.sol";
import { MessagingFee } from "@layerzerolabs/lz-evm-protocol-v2/contracts/interfaces/ILayerZeroEndpointV2.sol";

contract CTKN is OFT {
    constructor(
        string memory _name, // token name
        string memory _symbol, // token symbol
        address _lzEndpoint, // LayerZero Endpoint address
        address _delegate
    ) OFT(_name, _symbol, _lzEndpoint, _delegate){
        // your contract logic here
        _mint(_msgSender(), 100 * 10 * decimals()); // mints 100 tokens to the deployer
    }


    function quoteSend(
        SendParam calldata _sendParam,
        bool _payInLzToken
    ) override external view virtual returns (MessagingFee memory msgFee) {
        // @dev mock the amount to receive, this is the same operation used in the send().
        // The quote is as similar as possible to the actual send() operation.
        (, uint256 amountReceivedLD) = _debitView(_sendParam.amountLD, _sendParam.minAmountLD, _sendParam.dstEid);

        // @dev Builds the options and OFT message to quote in the endpoint.
        (bytes memory message, bytes memory options) = _buildMsgAndOptions(_sendParam, amountReceivedLD);

        // @dev Calculates the LayerZero fee for the send() operation.
        return _quote(_sendParam.dstEid, message, options, _payInLzToken);
    }

    function mint(address _to, uint256 _amount) public {
        _mint(_to, _amount);
    }

    // @dev expose internal functions for testing purposes
    function debit(
        uint256 _amountToSendLD,
        uint256 _minAmountToCreditLD,
        uint32 _dstEid
    ) public returns (uint256 amountDebitedLD, uint256 amountToCreditLD) {
        return _debit(_amountToSendLD, _minAmountToCreditLD, _dstEid);
    }

    function debitView(
        uint256 _amountToSendLD,
        uint256 _minAmountToCreditLD,
        uint32 _dstEid
    ) public view returns (uint256 amountDebitedLD, uint256 amountToCreditLD) {
        return _debitView(_amountToSendLD, _minAmountToCreditLD, _dstEid);
    }

    function removeDust(uint256 _amountLD) public view returns (uint256 amountLD) {
        return _removeDust(_amountLD);
    }

    function toLD(uint64 _amountSD) public view returns (uint256 amountLD) {
        return _toLD(_amountSD);
    }

    function toSD(uint256 _amountLD) public view returns (uint64 amountSD) {
        return _toSD(_amountLD);
    }

    function credit(address _to, uint256 _amountToCreditLD, uint32 _srcEid) public returns (uint256 amountReceivedLD) {
        return _credit(_to, _amountToCreditLD, _srcEid);
    }

    function buildMsgAndOptions(
        SendParam calldata _sendParam,
        uint256 _amountToCreditLD
    ) public view returns (bytes memory message, bytes memory options) {
        return _buildMsgAndOptions(_sendParam, _amountToCreditLD);
    }
}
